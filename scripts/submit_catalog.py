#!/usr/bin/env python3
"""Refuse retired autonomous catalog submission under Zed's contribution policy."""

import sys


def main():
    print(
        "Autonomous Zed catalog submission is disabled. Use prepare_catalog.py to "
        "save the verified patch, then have a human maintainer write and submit the PR. "
        "Policy: https://github.com/zed-industries/extensions/blob/main/AI_POLICY.md",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
