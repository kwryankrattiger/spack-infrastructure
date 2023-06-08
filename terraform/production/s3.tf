resource "aws_iam_role" "gitlab_runner_role" {
  # TODO
}

resource "kubectl_manifest" "gitlab_runner_service_account" {
  yaml_body = <<-YAML
    apiVersion: v1
    kind: ServiceAccount
    metadata:
      name: runner
      namespace: pipeline
      annotations:
          eks.amazonaws.com/role-arn: ${aws_iam_role.gitlab_runner_role.role_arn}
  YAML
}


locals {
  s3_bucket_policy_patterns = {
    "spack-binaries" : {
      "resources" : [
        "arn:aws:s3:::spack-binaries/*/armpl-*",
        "arn:aws:s3:::spack-binaries/*/intel-*"
      ]
      "allowed" : "${aws_iam_role.gitlab_runner_role.role_arn}"
    }

    "spack-binaries-prs" : {
      "resources" : [
        "arn:aws:s3:::spack-binaries-prs/*/armpl-*",
        "arn:aws:s3:::spack-binaries-prs/*/intel-*"
      ]
      "allowed" : "${aws_iam_role.gitlab_runner_role.role_arn}"
    }

    "spack-binaries-cray" : {
      "resources" : ["*"]
      "allowed" : "arn:aws:iam::588562868276:user/cray-binary-mirror"
    }
  }
}

resource "aws_s3_bucket_policy" "spack_binaries_protected_binaries_restricted" {
  for_each = local.s3_bucket_policy_patterns
  bucket   = each.key
  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Sid" : "PublicAccess",
        "Effect" : "Allow",
        "Principal" : "*",
        "Action" : "s3:GetObject",
        "Resource" : jsonencode(each.value.resources)
      }
    ]
  })
}

# data "aws_iam_policy_document" "protected_binaries" {
#   statement {
#     sid = "PublicAccess"
#     principals {
#       type = "AWS"
#       identifiers = ["*"]
#     }

#     actions = [
#       "s3:GetObject"
#     ]

#     resources = [
#      "arn:aws:s3:::${var.s3_bucket_name}/*"
#     ]
#   }
#   statement {
#     sid = "DenyAccessToProtectedData"
#     principals {
#       type = "AWS"
#       identifiers = ["*"]
#     }

#     effect = "Deny"

#     actions = [
#       "s3:GetObject"
#     ]

#     resources = ${locals.s3_bucket_policy[var.s3_bucket_name].resources}

#     condition {
#       test = "ArnNotLike"
#       variable = "aws:PrincipalArn"
#       values = "${locals.s3_bucket_policy[var.s3_bucket_name].allowed}"
#     }
#   }
#   statement {
#     sid = "AllowAccessToProtectedData"
#     principals {
#       type = "AWS"
#       identifiers = ["${locals.s3_bucket_policy[var.s3_bucket_name].allowed}"]
#     }

#     actions = [
#       "s3:GetObject"
#     ]

#     resources = ${locals.s3_bucket_policy[var.s3_bucket_name].resources}
#   }
# }
