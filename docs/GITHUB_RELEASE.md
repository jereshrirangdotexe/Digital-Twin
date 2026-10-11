# Publishing VoltMind

The clean `VoltMind_Open_Source` folder contains the application, original models, original synthetic data, demo, tests and documentation. Its companion full source ZIP contains actual data, not LFS pointers. It excludes dependencies, builds, uploads, local databases, session exports, personal project inventory and presentation files.

## GitHub Desktop

1. Install Git LFS. Extract the full source ZIP to a short writable path if needed.
2. Choose **File → Add local repository**, select the clean folder, and create a repository there if prompted.
3. Open its terminal and run `git lfs install` **before staging the first commit**. The supplied attributes select the larger datasets.
4. Review and commit the files. Choose **Publish repository** and turn off **Keep this code private** for a public release.
5. Check the published repository and Actions tab. A fresh clone needs Git LFS before installation.

## Terminal

Create an empty GitHub repository without an initial README/license, then use its URL:

```sh
git init -b main
git lfs install
git add .
git status --short
git lfs ls-files
git commit -m "Release VoltMind digital twin prototype"
git remote add origin <your-empty-github-repository-url>
git push -u origin main
```

Run `python scripts/prepare_github.py --check` before committing. The prepared copy is not automatically committed or pushed; no personal Git identity or repository URL is embedded.

Larger datasets use [Git LFS](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage). GitHub [blocks regular Git files above 100 MiB](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github). This release's largest original file is below that threshold, but LFS avoids storing large CSV revisions in normal history. Publish through a Git client rather than the browser uploader. LFS storage/bandwidth follow the account's applicable plan.

## Rebuild the package

From the working project:

```sh
python scripts/prepare_github.py --check
python scripts/prepare_github.py --output ../VoltMind_Open_Source_New
```

The destination must not exist. Export filters private/generated files, checks common credential patterns and verifies protected artifact SHA-256 values. It produces a clean folder, full source ZIP and package manifest. Automated scanning cannot guarantee recognition of every secret format or establish third-party rights.

Publishing preparation does not retrain models, alter original SCADA, change missing-data handling or reduce frontend features. Local databases and session logs remain in the existing working installation.
