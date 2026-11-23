#!/usr/bin/env python3
"""Isolated end-to-end smoke tests run against temporary copies of the repository."""

from __future__ import annotations

import os, shlex, shutil, subprocess, tempfile, time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COPY_IGNORE = shutil.ignore_patterns(".git", "config.toml", "*.local.*", ".env", ".env.*", "__pycache__", "*.pyc", ".pytest_cache")

def run(cmd: list[str], *, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a command with PROFILE stripped unless explicitly overridden."""
    merged = {k: v for k, v in os.environ.items() if k != "PROFILE"} | (env or {})
    return subprocess.run(cmd, env=merged, text=True, capture_output=True, check=check)

def copy_repo(dest: Path) -> Path:
    """Copy the repository without local overrides or git metadata into dest."""
    repo = dest / "repo"
    shutil.copytree(REPO_ROOT, repo, symlinks=True, ignore=COPY_IGNORE)
    return repo

def write_file(path: Path, content: str) -> Path:
    """Create parent directories and write text to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path

def test_config_prerequisites(repo: Path) -> None:
    """Verify missing config.toml, empty default_profile, --get, and strict precedence."""
    missing = run([str(repo / "bootstrap.sh")], check=False)
    assert missing.returncode != 0 and "cp config.example.toml config.toml" in missing.stderr, missing.stderr
    print("PASS Test 1: Missing config.toml fails with copy instruction")

    shutil.copy2(repo / "config.example.toml", repo / "config.toml")
    empty = run([str(repo / "bootstrap.sh")], check=False)
    assert empty.returncode != 0 and "No active profile resolved" in empty.stderr, empty.stderr
    print("PASS Test 2: Empty default_profile fails cleanly when PROFILE/--profile unset")

    read_cfg = ["python3", "-B", str(repo / "scripts/read-config.py"), "--config", str(repo / "config.toml")]
    assert run([*read_cfg, "--get", "core.username"]).stdout.strip() == "dev"

    cfg_text = (repo / "config.toml").read_text().replace('default_profile = ""', 'default_profile = "default"', 1)
    cfg_text += '\n[profiles.work]\ngit_name = "Work User"\ngit_email = "work@example.com"\n\n[profiles.personal]\ngit_name = "Personal User"\ngit_email = "personal@example.com"\n'
    (repo / "config.toml").write_text(cfg_text)

    assert f"CFG_PROFILE={shlex.quote('default')}" in run(read_cfg).stdout.splitlines()
    assert f"CFG_PROFILE={shlex.quote('personal')}" in run(read_cfg, env={"PROFILE": "personal"}).stdout.splitlines()
    assert f"CFG_PROFILE={shlex.quote('work')}" in run([*read_cfg, "--profile", "work"], env={"PROFILE": "personal"}).stdout.splitlines()

    undef = run([*read_cfg, "--profile", "nonexistent"], check=False)
    assert undef.returncode != 0 and "is not defined" in undef.stderr, undef.stderr
    print("PASS Test 3: --get core.username and strict profile precedence (--profile > PROFILE > default_profile)")

def test_default_bootstrap_and_zsh(repo: Path, tmp_path: Path) -> None:
    """Verify built-in symlinks, .bak backups, idempotency, gitconfig.local, ~/.agents, and zsh."""
    home = tmp_path / "home_default"; (home / ".config").mkdir(parents=True)
    write_file(home / ".zshrc", "# pre-existing zshrc\n")
    write_file(home / ".gemini" / "antigravity-cli" / "stale.txt", "stale\n")
    run([str(repo / "bootstrap.sh"), "--profile", "work"], env={"HOME": str(home)})

    assert all((home / rel).is_symlink() and (home / rel).exists() for rel in (".zshrc", ".gitconfig", ".config/starship.toml", ".vimrc", ".tmux.conf"))
    assert (home / ".gemini" / "antigravity-cli").resolve() == (repo / "agent-configs" / "antigravity-cli").resolve()
    assert (home / ".gemini" / "config").resolve() == (repo / "agent-configs" / "antigravity-config").resolve()
    assert (home / ".agents").is_dir() and not (home / ".agents").is_symlink()
    assert (home / ".agents" / "skills").is_dir() and (home / ".agents" / "AGENTS.md").is_file()
    assert run(["git", "config", "--file", str(home / ".gitconfig.local"), "user.email"]).stdout.strip() == "work@example.com"
    assert run(["git", "config", "user.email"], env={"HOME": str(home)}).stdout.strip() == "work@example.com"
    assert "you@example.com" in (repo / "profiles" / "default" / "gitconfig").read_text()
    assert list(home.glob(".zshrc.bak.*")) and list((home / ".gemini").glob("antigravity-cli.bak.*"))

    bak_before = sorted(str(p) for p in home.rglob("*.bak.*"))
    time.sleep(1.1)
    run([str(repo / "bootstrap.sh"), "--profile", "work"], env={"HOME": str(home)})
    assert bak_before == sorted(str(p) for p in home.rglob("*.bak.*")), "Idempotent re-run created extra backups"
    print("PASS Test 4: Default symlinks, .bak backups, idempotency, gitconfig.local, ~/.agents, agent-configs")

    assert "ZSH_OK" in run(["zsh", "-c", "source ~/.zshrc && echo ZSH_OK"], env={"HOME": str(home)}).stdout
    assert "ZSH_MIN_OK" in run(["zsh", "-c", "source ~/.zshrc && echo ZSH_MIN_OK"], env={"HOME": str(home), "PATH": "/bin:/usr/bin"}).stdout
    print("PASS Test 5: Zsh startup clean under full PATH and restricted PATH")

def test_byo_external_sources(repo: Path, tmp_path: Path) -> None:
    """Verify BYO dotfiles precedence, external ~/.agents, agent-configs isolation, [env], and post_setup_script."""
    home = tmp_path / "home_byo"; home.mkdir()
    ext_dot, ext_agents, ext_cfg = tmp_path / "ext_dotfiles", tmp_path / "ext_agents", tmp_path / "ext_agent_cfg"

    write_file(ext_dot / "profiles" / "work" / "zshrc", "# external work zshrc\n")
    write_file(ext_dot / "profiles" / "default" / "gitconfig", "# external default gitconfig\n")
    write_file(repo / "profiles" / "work" / "gitconfig", "# local work gitconfig\n")
    post_sh = write_file(ext_dot / "post.sh", '#!/usr/bin/env bash\necho "ran:$DEVCONTAINER_PROFILE" > "$HOME/.post_setup_marker"\n')
    post_sh.chmod(0o755)

    (ext_agents / "skills").mkdir(parents=True)
    write_file(ext_agents / "AGENTS.md", "# external shared agents\n")
    for sub, fname, content in (("agy-cli", "settings.json", '{"external": true}\n'), ("agy-cfg", "AGENTS.md", "@~/.agents/AGENTS.md\n"), ("claude", "CLAUDE.md", "extra\n")):
        write_file(ext_cfg / sub / fname, content)

    byo_cfg = write_file(
        repo / "config.byo.toml",
        f'[core]\ndefault_profile = "work"\nusername = "dev"\n\n[profiles.work]\ngit_name = "BYO User"\ngit_email = "byo@example.com"\n\n'
        f'[sources]\ndotfiles_dir = "{ext_dot}"\npost_setup_script = "post.sh"\n\n[modules]\nlanguages = ["node", "python"]\ntools = ["fzf", "uv"]\n\n'
        f'[agents]\ndir = "{ext_agents}"\ntarget_dir = "~/.agents"\n\n[agents.agy]\nenabled = true\nconfig_dir = "{ext_cfg}"\n'
        f'settings = "agy-cli"\nconfig = "agy-cfg"\nextra_config_dir_1 = "claude"\n'
        f'target_settings_dir = "~/.gemini/antigravity-cli"\ntarget_config_dir = "~/.gemini/config"\ntarget_extra_dir_1 = "~/.claude"\n\n[env]\nSAMPLE_FLAG = "enabled"\n',
    )

    run([str(repo / "bootstrap.sh"), "--config", str(byo_cfg)], env={"HOME": str(home)})
    for dst, src in ((".zshrc", ext_dot / "profiles/work/zshrc"), (".gitconfig", repo / "profiles/work/gitconfig"), (".vimrc", repo / "shell/vimrc"),
                     (".gemini/antigravity-cli", ext_cfg / "agy-cli"), (".gemini/config", ext_cfg / "agy-cfg"), (".claude", ext_cfg / "claude")):
        assert (home / dst).resolve() == src.resolve()
    assert (home / ".agents").is_symlink() and (home / ".agents").resolve() == ext_agents.resolve()
    assert (home / ".post_setup_marker").read_text().strip() == "ran:work"
    assert "export SAMPLE_FLAG='enabled'" in (home / ".config" / "devcontainer" / "runtime.zsh").read_text()
    print("PASS Test 6: BYO external dotfiles, shared ~/.agents, agent-configs + extra dir, [env], post_setup_script")

def test_gitignore_whitelists(tmp_path: Path) -> None:
    """Verify git init ignores local/runtime state while tracking starter files."""
    git_repo = copy_repo(tmp_path / "git_check")
    run(["git", "-C", str(git_repo), "init", "-q"])
    shutil.copy2(git_repo / "config.example.toml", git_repo / "config.toml")
    ac = git_repo / "agent-configs"
    for p, txt in ((git_repo / ".env", "SECRET=1\n"), (git_repo / "test.local.toml", "[core]\n"), (ac / "antigravity-cli" / "cli.log", "log\n"),
                   (ac / "antigravity-cli" / "oauth-token", "tok\n"), (ac / "antigravity-config" / "mcp_config.json", "{}\n"), (ac / "antigravity-cli" / "brain" / "scratch.md", "tmp\n")):
        write_file(p, txt)

    status_out = run(["git", "-C", str(git_repo), "status", "--short"]).stdout
    for ignored in ("config.toml", ".env", "test.local.toml", "cli.log", "oauth-token", "mcp_config.json", "brain/"):
        assert ignored not in status_out, f"Ignored path leaked into git status: {ignored}\n{status_out}"

    run(["git", "-C", str(git_repo), "add", "-A"])
    staged = set(run(["git", "-C", str(git_repo), "diff", "--cached", "--name-only"]).stdout.splitlines())
    for expected in ("bootstrap.sh", "Dockerfile", "config.example.toml", "tests/smoke_test.py", "agent-configs/.gitignore",
                     "agent-configs/README.md", "agent-configs/antigravity-cli/settings.json", "agent-configs/antigravity-config/AGENTS.md", "agent-configs/antigravity-config/skills.json"):
        assert expected in staged, f"Missing expected tracked file: {expected}"
    print("PASS Test 7: git init + .gitignore / agent-configs/.gitignore whitelist tracks core & starter files")

def main() -> None:
    """Execute all isolated smoke tests in a temporary directory."""
    with tempfile.TemporaryDirectory(prefix="devcontainer-smoke-") as tmp:
        tmp_path = Path(tmp); repo = copy_repo(tmp_path)
        test_config_prerequisites(repo)
        test_default_bootstrap_and_zsh(repo, tmp_path)
        test_byo_external_sources(repo, tmp_path)
        test_gitignore_whitelists(tmp_path)
    print("ALL 7 SMOKE TESTS PASSED!")

if __name__ == "__main__":
    main()
