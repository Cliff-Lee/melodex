# Uploading this repository to GitHub

This folder is already laid out as a Git repository root.

## Option A — GitHub website

1. Create a new empty repository on GitHub, for example `melodex-provider-sdk`.
2. Do **not** ask GitHub to pre-create a README, license, or `.gitignore` because they are already included here.
3. Upload the contents of this folder, preserving folders such as `.github`, `docs`, `spec`, `src`, `tests`, and `examples`.

For a repository with many files, Git command line or GitHub Desktop is usually easier than browser upload.

## Option B — command line

From this folder:

```bash
git init
git add .
git commit -m "Initial public Melodex Provider SDK"
git branch -M main
git remote add origin https://github.com/YOUR-ACCOUNT/melodex-provider-sdk.git
git push -u origin main
```

## Recommended GitHub settings

After the first push:

- enable **Issues**;
- enable **Private vulnerability reporting** under Security;
- optionally enable branch protection/rules for `main` after CI is confirmed working;
- require the `test` workflow before merge;
- add topics such as `music`, `media-server`, `openapi`, `plugin-system`, `python`, and `llm`;
- keep Actions permissions at the least privilege needed by the included workflows.

## Before publishing

Read `RELEASE_CHECKLIST.md`, especially the secret scan and source-neutrality checks.
