# ruff: noqa: F403,F405
from .analysis import ensure_api_keys, render_analysis_workspace
from .common import *
from .guide import get_content_columns, render_sidebar_controls, render_usage_guide
from .layout import render_debug_tools, render_global_styles, render_navigation_shell
from .routes import route_page


def main():
    """主应用程序"""
    initialize_session_state()
    check_frontend_auth_cache()

    if not auth.is_authenticated():
        auth.render_login_page()
        return

    render_global_styles()
    render_debug_tools()
    page = render_navigation_shell()
    if route_page(page):
        return

    if not require_permission("analysis"):
        return

    api_status = check_api_keys()
    if not ensure_api_keys(api_status):
        return

    config = render_sidebar()
    show_guide = render_sidebar_controls()
    col1, col2 = get_content_columns(show_guide)
    render_analysis_workspace(col1, config)
    render_usage_guide(show_guide, col2)


if __name__ == "__main__":
    main()
