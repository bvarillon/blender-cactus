# GitHub Configuration

This directory contains GitHub-specific configuration files for the Blender Cactus project.

## Branch Protection

The main branch is protected to prevent direct pushes. All changes must go through pull requests.

### Current Protection Rules

- ✅ **Pull Request Required**: All commits must be made through pull requests
- ✅ **Approvals Required**: At least 1 approval is required before merging
- ✅ **Status Checks**: All CI checks must pass before merging
- ✅ **No Force Pushes**: Force pushes are blocked
- ✅ **No Deletions**: Branch deletion is blocked
- ✅ **Conversation Resolution**: All discussions must be resolved before merging

### How to Configure Branch Protection

#### Option 1: Using GitHub UI

1. Go to **Settings** > **Branches** > **Branch protection rules**
2. Click **Add rule**
3. Enter `main` as the branch name pattern
4. Enable the following options:
   - ✅ Require a pull request before merging
     - Require approvals: 1
     - Dismiss stale pull request approvals when new commits are pushed
   - ✅ Require status checks to pass before merging
     - Require branches to be up to date before merging
   - ✅ Include administrators
   - ✅ Restrict who can push to matching branches (leave empty)
   - ✅ Block force pushes
   - ✅ Block deletions
   - ✅ Require conversation resolution before merging

#### Option 2: Using GitHub CLI

```bash
# Apply branch protection from the configuration file
gh api -X PUT repos/{owner}/{repo}/branches/main/protection -f @.github/branch-protection.yml
```

#### Option 3: Run the Setup Workflow

1. Go to **Actions** > **Setup Branch Protection**
2. Click **Run workflow**
3. Select the branch and click **Run workflow**

## CI/CD Workflows

### 1. Protect Main Branch (`protect-main.yml`)

- **Trigger**: Push to `main` branch
- **Purpose**: Block direct pushes that are not merge commits
- **Action**: Fails if the push is not from a merged pull request

### 2. Auto Version & Release (`release.yml`)

- **Trigger**: Push to `main` branch (after PR merge)
- **Purpose**: Automatically determine version bump and create release
- **Version Bump Rules**:
  - `feat:` or `feature:` → **MINOR** version bump (0.x.0 → 0.x+1.0)
  - `fix:` → **PATCH** version bump (0.0.x → 0.0.x+1)
  - `BREAKING CHANGE:` or `!` → **MAJOR** version bump (x.0.0 → x+1.0.0)
  - Any other commit → **PATCH** version bump
- **Actions**:
  - Analyzes commits since last tag
  - Determines version bump type
  - Creates new Git tag
  - Creates GitHub Release
  - Updates version in pyproject.toml files

### 3. Setup Branch Protection (`setup-protection.yml`)

- **Trigger**: 
  - Manual (workflow_dispatch)
  - Push to `.github/branch-protection.yml`
- **Purpose**: Configure branch protection via GitHub API
- **Note**: Requires admin permissions

## Versioning Strategy

This project uses **Semantic Versioning 2.0.0** (SemVer).

### Version Format

`MAJOR.MINOR.PATCH`

- **MAJOR**: Incremented for backward-incompatible changes
- **MINOR**: Incremented for new backward-compatible features
- **PATCH**: Incremented for backward-compatible bug fixes

### Commit Message Convention

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
type(scope): description

body

footer
```

#### Common Types

- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests
- `chore`: Changes to the build process or auxiliary tools
- `revert`: Revert a previous commit

#### Breaking Changes

Add `!` after the type/scope or include `BREAKING CHANGE:` in the footer:

```
feat!: breaking change

BREAKING CHANGE: This feature introduces a breaking change
```

### Examples

```bash
# Minor version bump (feature)
git commit -m "feat: Add WebSocket communication"

# Patch version bump (bug fix)
git commit -m "fix: Handle connection timeout"

# Major version bump (breaking change)
git commit -m "feat!: Change API endpoint structure"
# or
git commit -m "feat: Change API endpoint structure

BREAKING CHANGE: API endpoints have been restructured"
```

## Workflow Summary

1. **Create a feature branch**: `git checkout -b feat/my-feature`
2. **Make changes and commit**: Use conventional commit messages
3. **Push to remote**: `git push origin feat/my-feature`
4. **Create Pull Request**: Target `main` branch
5. **Get approvals**: At least 1 approval required
6. **Merge PR**: Squash merge or merge commit
7. **Auto-release**: CI/CD creates tag and release automatically

## Troubleshooting

### "Direct pushes to main are not allowed"

This is expected behavior. To contribute:
1. Create a new branch
2. Make your changes
3. Create a pull request
4. Get approvals
5. Merge

### Workflow permissions issues

If workflows fail with permission errors:
1. Go to **Settings** > **Actions** > **General**
2. Under **Workflow permissions**, enable **Read and write permissions**
3. Or create a Personal Access Token (PAT) with `repo` scope and use it as a secret

### Version not bumping correctly

Check your commit messages:
- Use lowercase types (`feat:`, not `Feat:`)
- Include the colon (`feat:`, not `feat`)
- For breaking changes, use `!` or `BREAKING CHANGE:`

## Additional Resources

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [GitHub Branch Protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub Actions](https://docs.github.com/en/actions)
