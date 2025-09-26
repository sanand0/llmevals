# Prompts

## Generate run.sh

Update the (nearly empty) bash script `run.sh` to:

- Read each line in `developer-styles.tsv` and pick up the DEVELOPER (first column) and STYLE (second column)
- For each line, replace the $DEVELOPER and $STYLE in `prompt-template.md` with these values
- Pipe the output through `llm prompt --extract -m gpt-5-mini` and save the output as $DEVELOPER.js

No tests required.
