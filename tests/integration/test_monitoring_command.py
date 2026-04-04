"""Integration tests for the 'monitoring' command."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.integration.conftest import (
    ROOT,
    COMBINATIONS,
    create_fake_package_managers,
    run_cli_create,
)


def run_cli_monitoring(project_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    cmd = [
        sys.executable,
        "-m",
        "cli",
        "monitoring",
        str(project_path),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def _scaffold_monitoring(tmp_path: Path, design: str, orm: str) -> Path:
    project_dir = tmp_path / f"{design}-{orm}-monitoring"
    fake_bin = create_fake_package_managers(tmp_path)
    run_cli_create(project_dir, design, orm, app_name="monitor-app", bin_dir=fake_bin)
    result = run_cli_monitoring(project_dir)
    assert result.returncode == 0, result.stderr
    return project_dir


@pytest.mark.integration
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_monitoring_creates_expected_files(
    tmp_path: Path, design: str, orm: str
) -> None:
    project_dir = _scaffold_monitoring(tmp_path, design, orm)

    assert (project_dir / "docker-compose.monitoring.yml").exists()
    assert (
        project_dir / "compose" / "monitoring" / "alloy" / "config.alloy"
    ).exists()
    assert (
        project_dir / "compose" / "monitoring" / "prometheus" / "prometheus.yml"
    ).exists()
    assert (
        project_dir
        / "compose"
        / "monitoring"
        / "grafana"
        / "datasources"
        / "loki.yaml"
    ).exists()
    assert (
        project_dir
        / "compose"
        / "monitoring"
        / "grafana"
        / "datasources"
        / "prometheus.yaml"
    ).exists()
    assert (
        project_dir
        / "compose"
        / "monitoring"
        / "grafana"
        / "provisioning"
        / "dashboards.yaml"
    ).exists()
    assert (
        project_dir
        / "compose"
        / "monitoring"
        / "grafana"
        / "dashboards"
        / "logs.json"
    ).exists()
    assert (
        project_dir
        / "compose"
        / "monitoring"
        / "grafana"
        / "dashboards"
        / "metrics.json"
    ).exists()


@pytest.mark.integration
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_monitoring_compose_file_content(
    tmp_path: Path, design: str, orm: str
) -> None:
    project_dir = _scaffold_monitoring(tmp_path, design, orm)
    compose = (project_dir / "docker-compose.monitoring.yml").read_text()

    assert "grafana/loki" in compose
    assert "grafana/alloy" in compose
    assert "grafana/grafana" in compose
    assert "prom/prometheus" in compose
    assert "loki-data" in compose
    assert "prometheus-data" in compose
    assert "grafana-data" in compose
    assert "--web.enable-remote-write-receiver" in compose


@pytest.mark.integration
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_monitoring_alloy_config_content(
    tmp_path: Path, design: str, orm: str
) -> None:
    project_dir = _scaffold_monitoring(tmp_path, design, orm)
    alloy_config = (
        project_dir / "compose" / "monitoring" / "alloy" / "config.alloy"
    ).read_text()

    assert 'values = ["app"]' in alloy_config
    assert "loki.source.docker" in alloy_config
    assert "loki.write" in alloy_config
    assert "loki:3100" in alloy_config
    assert "prometheus.scrape" in alloy_config
    assert "prometheus.remote_write" in alloy_config
    assert "prometheus:9090" in alloy_config
    assert 'metrics_path    = "/metrics"' in alloy_config
    assert 'job_name        = "app"' in alloy_config


@pytest.mark.integration
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_monitoring_grafana_datasource_content(
    tmp_path: Path, design: str, orm: str
) -> None:
    project_dir = _scaffold_monitoring(tmp_path, design, orm)
    loki_ds = (
        project_dir
        / "compose"
        / "monitoring"
        / "grafana"
        / "datasources"
        / "loki.yaml"
    ).read_text()
    prometheus_ds = (
        project_dir
        / "compose"
        / "monitoring"
        / "grafana"
        / "datasources"
        / "prometheus.yaml"
    ).read_text()

    # Loki datasource
    assert "type: loki" in loki_ds
    assert "uid: loki" in loki_ds
    assert "http://loki:3100" in loki_ds
    assert "isDefault: true" in loki_ds
    assert "orgId: 1" in loki_ds
    assert "editable: false" in loki_ds
    assert "maxLines: 1000" in loki_ds
    assert "X-Scope-OrgID" in loki_ds

    # Prometheus datasource
    assert "type: prometheus" in prometheus_ds
    assert "uid: prometheus" in prometheus_ds
    assert "http://prometheus:9090" in prometheus_ds
    assert "isDefault: false" in prometheus_ds
    assert "orgId: 1" in prometheus_ds
    assert "editable: false" in prometheus_ds
    assert "httpMethod: POST" in prometheus_ds
    assert "prometheusType: Prometheus" in prometheus_ds
    assert "cacheLevel: High" in prometheus_ds


@pytest.mark.integration
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_monitoring_prometheus_config_content(
    tmp_path: Path, design: str, orm: str
) -> None:
    project_dir = _scaffold_monitoring(tmp_path, design, orm)
    prometheus_cfg = (
        project_dir / "compose" / "monitoring" / "prometheus" / "prometheus.yml"
    ).read_text()

    assert "scrape_interval" in prometheus_cfg
    assert "scrape_configs" in prometheus_cfg


@pytest.mark.integration
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_monitoring_injects_metrics_route_file(
    tmp_path: Path, design: str, orm: str
) -> None:
    project_dir = _scaffold_monitoring(tmp_path, design, orm)

    if design == "ddd":
        metrics_path = (
            project_dir / "src" / "app" / "presentation" / "metrics.py"
        )
    else:
        metrics_path = project_dir / "src" / "app" / "views" / "metrics.py"

    assert metrics_path.exists()
    content = metrics_path.read_text()
    assert "generate_latest" in content
    assert "CONTENT_TYPE_LATEST" in content
    assert '"/metrics"' in content


@pytest.mark.integration
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_monitoring_registers_metrics_route(
    tmp_path: Path, design: str, orm: str
) -> None:
    project_dir = _scaffold_monitoring(tmp_path, design, orm)

    if design == "ddd":
        registry_path = (
            project_dir / "src" / "app" / "presentation" / "__init__.py"
        )
    else:
        registry_path = project_dir / "src" / "app" / "urls.py"

    content = registry_path.read_text()
    assert "metrics" in content
    assert "metrics.register(app)" in content


@pytest.mark.integration
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_monitoring_adds_prometheus_client_dependency(
    tmp_path: Path, design: str, orm: str
) -> None:
    project_dir = _scaffold_monitoring(tmp_path, design, orm)
    pyproject = (project_dir / "pyproject.toml").read_text()
    assert "prometheus-client" in pyproject


@pytest.mark.integration
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_monitoring_logs_dashboard_content(
    tmp_path: Path, design: str, orm: str
) -> None:
    project_dir = _scaffold_monitoring(tmp_path, design, orm)
    content = (
        project_dir / "compose" / "monitoring" / "grafana" / "dashboards" / "logs.json"
    ).read_text()

    assert '"robyn-app-logs"' in content
    assert '"type": "logs"' in content
    assert '"type": "textbox"' in content
    assert '"search"' in content
    assert '"uid": "loki"' in content
    assert 'job=\\"app\\"' in content
    assert '"stream"' in content
    assert '"value": ".*"' in content
    assert "__inputs" not in content
    assert "${DS_LOKI}" not in content


@pytest.mark.integration
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_monitoring_metrics_dashboard_content(
    tmp_path: Path, design: str, orm: str
) -> None:
    project_dir = _scaffold_monitoring(tmp_path, design, orm)
    content = (
        project_dir / "compose" / "monitoring" / "grafana" / "dashboards" / "metrics.json"
    ).read_text()

    assert '"robyn-app-metrics"' in content
    assert '"uid": "prometheus"' in content
    assert "process_cpu_seconds_total" in content
    assert "process_resident_memory_bytes" in content
    assert "process_open_fds" in content
    assert "python_gc_collections_total" in content
    assert "python_info" in content
    assert "process_start_time_seconds" in content
    assert "__inputs" not in content
    assert "${DS_PROMETHEUS}" not in content


@pytest.mark.integration
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_monitoring_compose_mounts_dashboards(
    tmp_path: Path, design: str, orm: str
) -> None:
    project_dir = _scaffold_monitoring(tmp_path, design, orm)
    compose = (project_dir / "docker-compose.monitoring.yml").read_text()

    assert "provisioning/dashboards" in compose
    assert "/var/lib/grafana/dashboards" in compose


@pytest.mark.integration
def test_monitoring_fails_on_non_robyn_project(tmp_path: Path) -> None:
    non_robyn = tmp_path / "non-robyn"
    non_robyn.mkdir()
    (non_robyn / "pyproject.toml").write_text("[project]\nname = 'other'\n")

    result = run_cli_monitoring(non_robyn)

    assert result.returncode != 0
    assert "robyn-config" in result.stderr
