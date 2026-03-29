from logic.runtime_bootstrap import configure_tk_runtime


if __name__ == "__main__":
    configure_tk_runtime()
    from ui.dashboard import run_app

    run_app()
