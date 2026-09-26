# Publish Melodex to GitHub

The intended public repository is:

`https://github.com/Cliff-Lee/melodex`

Before publishing, run:

```bash
python3 scripts/release_check.py
```

## Fastest method — GitHub CLI

Install/authenticate GitHub CLI once, then from the repository root run:

```bash
./scripts/publish_github.sh
```

The script will:

1. run the public-release audit;
2. initialise Git if necessary;
3. create the initial commit;
4. create `Cliff-Lee/melodex` as a public GitHub repository if it does not already exist;
5. push `main`.

To publish under a different account/name:

```bash
./scripts/publish_github.sh YOUR-ACCOUNT YOUR-REPOSITORY
```

## Manual Git method

Create an empty public repository named `melodex` on GitHub, then:

```bash
git init
git add .
git commit -m "Initial public Melodex release"
git branch -M main
git remote add origin https://github.com/Cliff-Lee/melodex.git
git push -u origin main
```

## First downloadable release

After GitHub Actions passes:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The release workflows build the supported platform artifacts defined in `.github/workflows/`.
