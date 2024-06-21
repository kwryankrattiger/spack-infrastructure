# Generated by Django 4.2.4 on 2024-05-21 17:07

from django.db import migrations

RAW_SQL = """
BEGIN;

-- This table is odd because it has one boolean column, so a maximum of two rows
INSERT INTO core_timerdatadimension (
    cache
)
VALUES
    (TRUE),
    (FALSE)
;


-- Ensure all types of phases exist in this dimension
INSERT INTO core_timerphasedimension (
    path,
    is_subphase
)
SELECT
    DISTINCT ON (path)

    path,
    is_subphase
FROM core_timerphase
;
-- Takes ~3 minutes, Scans ~240M rows, Inserts 21 rows


-- Ensure that for all timer facts an entry in the package dimension
-- exists that consists of the package name with all other columns empty.
INSERT INTO core_packagedimension (name)
SELECT DISTINCT (name)
FROM core_timer
ON CONFLICT DO NOTHING
;


-- Create all timer facts from the existing timer table
INSERT INTO core_timerfact (
    job_id,
    date_id,
    time_id,
    timer_data_id,
    package_id,
    spec_id,
    total_duration
)
SELECT
    core_timer.job_id,
    to_char(core_job.started_at, 'YYYYMMDD')::int,
    to_char(core_job.started_at, 'HH24MISS')::int,
    tdd.id,
    pd.name,
    COALESCE(
        psd.id,
        (SELECT id FROM core_packagespecdimension WHERE hash = '')
    ),
    time_total
FROM core_timer
INNER JOIN core_job ON
        core_timer.job_id       = core_job.job_id
INNER JOIN core_timerdatadimension tdd ON
    core_timer.cache = tdd.cache
INNER JOIN core_packagedimension pd ON
    pd.name = core_timer.name
LEFT JOIN core_packagespecdimension psd ON
    psd.hash = core_timer.hash

-- There are ~3k entries that are duplicate in all dimensions
ON CONFLICT DO NOTHING
;
-- Takes ~1 hour, Inserts ~50M rows


-- This query seems scary but it's just creating the upper and lower
-- ID ranges that determine each batch
CREATE TEMP TABLE batches AS (
    SELECT
        lower,
        upper
    FROM (
        SELECT
            id as lower,
            LEAD(id, 1) OVER () as upper
        FROM (
            SELECT generate_series(
                0,
                (FLOOR((MAX(core_timerphase.id) + 5000000) / 5000000)*5000000)::bigint,
                5000000
            ) as id FROM core_timerphase
        ) it
    ) ot
    WHERE ot.upper IS NOT NULL
);

-- Use procedure and for loop to run inserts in batches, to prevent memory / disk issues
DO
$body$
DECLARE
    batch RECORD;
BEGIN
    FOR batch in SELECT * FROM batches ORDER BY LOWER
    LOOP
        INSERT INTO core_timerphasefact (
            job_id,
            date_id,
            time_id,
            timer_data_id,
            package_id,
            spec_id,
            phase_id,
            duration,
            ratio_of_total
        )
        SELECT
            core_timer.job_id,
            to_char(core_job.started_at, 'YYYYMMDD')::int,
            to_char(core_job.started_at, 'HH24MISS')::int,
            tdd.id,
            pd.name,
            -- Default to the "empty spec" if join failed
            COALESCE(
                psd.id,
                (SELECT id FROM core_packagespecdimension WHERE hash = '')
            ),
            tpd.id,
            seconds,
            seconds / time_total
        FROM core_timerphase
        LEFT JOIN
            core_timer ON core_timerphase.timer_id = core_timer.id
        LEFT JOIN
            core_job ON core_timer.job_id = core_job.job_id
        LEFT JOIN core_timerdatadimension tdd ON
            core_timer.cache = tdd.cache
        LEFT JOIN core_packagedimension pd ON
            core_timer.name = pd.name
        LEFT JOIN core_packagespecdimension psd ON
            psd.hash = core_timer.hash
        LEFT JOIN core_timerphasedimension tpd ON
            core_timerphase.path = tpd.path
        WHERE
                core_timerphase.id > batch.lower
            AND core_timerphase.id <= batch.upper

        -- There are ~13k duplicate rows
        ON CONFLICT DO NOTHING
        ;
    END LOOP;
END;
$body$
LANGUAGE 'plpgsql'
;
-- Took 3.6 hours, scanned ~240M rows + joins, inserted ~240M rows


-- Final commit
COMMIT;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0016_timer_models"),
    ]

    operations = [migrations.RunSQL(RAW_SQL, reverse_sql="")]