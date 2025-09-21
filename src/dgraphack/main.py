#!/usr/bin/env python3

import os
import webbrowser
from uuid import uuid4

import uvicorn

from dgraphack.consts import API_PORT, API_URL, API_WORK_DIR


def ensure_api_is_running(args) -> None:
	# TODO: Refactor hard-coded host out
	uvicorn.run("dgraphack.api:app", host="0.0.0.0", port=API_PORT, reload=args.reload)


def launch_editor(args) -> None:
	# Create a directory for our session, and link our local file there.
	sessionid = str(uuid4())
	session_path = os.path.join(API_WORK_DIR, sessionid)
	os.makedirs(session_path)
	os.symlink(
		os.path.abspath(args.file),
		os.path.join(session_path,"filelink.dot"),
	)

	# Launch a web browser ($BROWSER or --browser) to our session in the API.
	session_url = f"{API_URL}/?sessionid={sessionid}"
	if args.browser is None:
		webbrowser.open(session_url)
	else:
		webbrowser.get(args.browser).open(session_url)


def main() -> None:
	import argparse
	arg_parser = argparse.ArgumentParser(exit_on_error=True)
	sub_parsers = arg_parser.add_subparsers(required=True)

	# API
	parser_api = sub_parsers.add_parser(
		'api',
		help='run the API',
	)
	parser_api.add_argument("--reload", action='store_true')
	parser_api.set_defaults(func=ensure_api_is_running)

	# Edit
	parser_edit = sub_parsers.add_parser(
		'edit',
		help='connect to the API and run the editor in a browser',
	)
	parser_edit.add_argument("--browser", "-b", type=str, required=False)
	parser_edit.add_argument("file", type=str)
	parser_edit.set_defaults(func=launch_editor)

	args = arg_parser.parse_args()

	# Delegate execution to subcommand.
	args.func(args)


if __name__ == "__main__":
    main()

