from logic.runtime_bootstrap import configure_tk_runtime


if __name__ == "__main__":
    configure_tk_runtime()
    from ui.remote_admin import run_remote_admin

    run_remote_admin()
