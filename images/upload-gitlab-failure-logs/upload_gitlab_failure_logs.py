from datetime import datetime
import json
import os
import re
from pathlib import Path

import yaml

GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN")
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT")
OPENSEARCH_USERNAME = os.environ.get("OPENSEARCH_USERNAME")
OPENSEARCH_PASSWORD = os.environ.get("OPENSEARCH_PASSWORD")


def load_taxonomy():
    with open(Path(__file__).parent / "taxonomy.yaml") as f:
        data = yaml.safe_load(f)["taxonomy"]
    return data


taxonomy = load_taxonomy()


def classify(job_trace: str):
    job_error_class = None
    matching_patterns = set()
    for error_class, lookups in taxonomy["error_classes"].items():
        if lookups:
            for grep_expr in lookups.get("grep_for", []):
                if re.compile(grep_expr).search(job_trace):
                    matching_patterns.add(error_class)

    # If the job logs matched any regexes, assign it the taxonomy
    # with the highest priority in the "deconflict order".
    # Otherwise, assign it a taxonomy of "other".
    if len(matching_patterns):
        for error_class in taxonomy["deconflict_order"]:
            if error_class in matching_patterns:
                job_error_class = error_class
                break
    else:
        job_error_class = "other"

    return job_error_class


def main():
    import gitlab
    from opensearch_dsl import Date, Document, connections

    class JobPayload(Document):
        timestamp = Date()

        class Index:
            name = "gitlab-job-failures-*"

        def save(self, **kwargs):
            # assign now if no timestamp given
            if not self.timestamp:
                self.timestamp = datetime.now()

            # override the index to go to the proper timeslot
            kwargs["index"] = self.timestamp.strftime("gitlab-job-failures-%Y%m%d")
            return super().save(**kwargs)

    job_input_data = json.loads(os.environ["JOB_INPUT_DATA"])
    job_input_data["error_taxonomy_version"] = taxonomy["version"]

    # Convert all string timestamps in webhook payload to `datetime` objects
    for key, val in job_input_data.items():
        try:
            if isinstance(val, str):
                job_input_data[key] = datetime.strptime(val, "%Y-%m-%d %H:%M:%S %Z")
        except ValueError:
            continue

    gl = gitlab.Gitlab("https://gitlab.spack.io", GITLAB_TOKEN)

    connections.create_connection(
        hosts=[OPENSEARCH_ENDPOINT],
        http_auth=(
            OPENSEARCH_USERNAME,
            OPENSEARCH_PASSWORD,
        ),
    )

    job_id = job_input_data["build_id"]
    project_id = job_input_data["project_id"]

    project = gl.projects.get(project_id)
    job = project.jobs.get(job_id)
    job_trace: str = job.trace().decode()  # type: ignore

    job_error_class = classify(job_trace)

    if job_error_class == "other":
        # If this job timed out or failed to be scheduled by GitLab,
        # label it as such.
        if job_input_data["build_failure_reason"] in (
            "stuck_or_timeout_failure",
            "scheduler_failure",
        ):
            job_error_class = job_input_data["build_failure_reason"]

    job_input_data["error_taxonomy"] = job_error_class

    # Upload to OpenSearch
    doc = JobPayload(**job_input_data)
    doc.save()


if __name__ == "__main__":
    main()
