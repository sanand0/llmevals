#!/usr/bin/env bash

# Generate code in different developer styles using OpenAI Codex

set -euo pipefail

# Read the TSV file line by line
while IFS=$'\t' read -r GITHUB DEVELOPER STYLE; do
  # Skip if output directory already exists
  if [[ -d "${GITHUB}" ]]; then
    continue
  fi

  mkdir -p "${GITHUB}"
  cd "${GITHUB}"

  # Generate the file using the template and OpenAI Codex
  GITHUB="$GITHUB" DEVELOPER="$DEVELOPER" STYLE="$STYLE" envsubst '$GITHUB $DEVELOPER $STYLE' < ../template.md \
    | npx -y @openai/codex exec --full-auto -

  cd ..
done < developer-styles.tsv
