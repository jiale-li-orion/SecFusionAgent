from apps.runtime_models import register_runtime_models
from packages.monitoring.data_plane_status import main

if __name__ == "__main__":
    register_runtime_models()
    main()
