# Parallel backend and frontend development startup

## Goal

Provide one-command development startup for both application layers while preserving Docker Compose as a separate, reproducible option.

## Design

The local workflow will use `scripts/start-dev.ps1`. It runs FastAPI from the repository root and Next.js from the `frontend` directory as child processes, inherits the current environment (including `.env`-driven backend settings and `NEXT_PUBLIC_API_URL`), keeps both logs visible, and cleans up the sibling process when the script exits or either service stops. It will prefer the repository virtual-environment Python executable and fail with a useful message when required executables or the frontend dependencies are unavailable.

The container workflow will use the existing `docker-compose.yml` local profile. A Make target will expose the same workflow as a discoverable command without changing service topology, ports, health checks, or the synthetic-only data boundary.

## User-facing commands

```powershell
# Local Windows development
.\scripts\start-dev.ps1

# Docker development
docker compose --profile local up --build
# or
make demo-up
```

The local workflow serves the frontend at `http://localhost:3000` and backend at `http://localhost:8000`; the Docker workflow exposes the same ports.

## Failure handling

The local launcher validates the repository, Python executable, and `frontend\package.json` before starting. If either child process exits, the other is terminated and the launcher returns a non-zero exit code. Ctrl+C and script termination also terminate both children. The launcher does not silently create databases or alter production configuration.

## Documentation and verification

README and the quick-start guide will show both workflows and clearly state that the synthetic database must exist for the clinical demo. Verification will cover PowerShell script structure and run the existing frontend tests/build plus backend checks that are practical in the current environment; Docker startup will be validated structurally when Docker is unavailable.
