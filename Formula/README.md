# Homebrew formula

Self-hosted Homebrew tap for `rename`.

## Install via tap

```bash
brew tap study8677/rename https://github.com/study8677/rename.git
brew install rename
```

Then enable the background service (alternative to `rename install`):

```bash
brew services start rename
```

The formula installs `rename` as a Python virtualenv-isolated CLI and
optionally launches the renamer as a `brew services`-managed daemon.

## For maintainers

When cutting a new release:

1. `git tag vX.Y.Z && git push --tags`
2. `gh release create vX.Y.Z ...`
3. Get the tarball SHA256:
   ```bash
   curl -sL https://github.com/study8677/rename/archive/refs/tags/vX.Y.Z.tar.gz \
     | shasum -a 256
   ```
4. Update `url` and `sha256` in `Formula/rename.rb` and commit.

The bottle-less install builds in seconds on Apple Silicon — no need to ship
binary bottles for a pure-Python project.
