module "s3_bucket" {
  source  = "terraform-aws-modules/s3-bucket/aws"
  version = "3.11.1"
}

locals {
  s3_bucket_policy_patterns = {
    "spack-binaries": {
      "resources": [
        "arn:aws:s3:::spack-binaries/*/armpl-*",
        "arn:aws:s3:::spack-binaries/*/intel-*"
      ]
      "allowed": "${module.eks.eks_managed_node_groups["initial"].iam_role_arn}"
    }

    "spack-binaries-prs": {
      "resources": [
        "arn:aws:s3:::spack-binaries-prs/*/armpl-*",
        "arn:aws:s3:::spack-binaries-prs/*/intel-*"
      ]
      "allowed": "${module.eks.eks_managed_node_groups["initial"].iam_role_arn}"
    }

    "spack-binaries-cray": {
      "resources": ["*"]
      "allowed": "arn:aws:iam::588562868276:user/cray-binary-mirror"
    }
  }
}

resource "aws_s3_bucket_policy" "spack_binaries_protected_binaries_restricted" {
  bucket = "spack-binaries"
  policy = data.aws_iam_policy_document.protected_binaries.json
}

resource "aws_s3_bucket_policy" "spack_binaries_prs_protected_binaries_restricted" {
  bucket = "spack-binaries-prs"
  policy = data.aws_iam_policy_document.protected_binaries.json
}

resource "aws_s3_bucket_policy" "spack_binaries_cray_protected_binaries_restricted" {
  bucket = "spack-binaries-cray"
  policy = data.aws_iam_policy_document.protected_binaries.json
}

data "aws_iam_policy_document" "protected_binaries" {
  statement {
    sid = "PublicAccess"
    principals {
      type = "AWS"
      identifiers = ["*"]
    }

    actions = [
      "s3:GetObject"
    ]

    resources = [
     "arn:aws:s3:::${var.s3_bucket_name}/*"
    ]
  }
  statement {
    sid = "DenyAccessToProtectedData"
    principals {
      type = "AWS"
      identifiers = ["*"]
    }

    effect = "Deny"

    actions = [
      "s3:GetObject"
    ]

    resources = ${locals.s3_bucket_policy[var.s3_bucket_name].resources}

    condition {
      test = "ArnNotLike"
      variable = "aws:PrincipalArn"
      values = "${locals.s3_bucket_policy[var.s3_bucket_name].allowed}"
    }
  }
  statement {
    sid = "AllowAccessToProtectedData"
    principals {
      type = "AWS"
      identifiers = ["${locals.s3_bucket_policy[var.s3_bucket_name].allowed}"]
    }

    actions = [
      "s3:GetObject"
    ]

    resources = ${locals.s3_bucket_policy[var.s3_bucket_name].resources}
  }
}
