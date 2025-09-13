#!/usr/bin/env python3

import asyncio
import concurrent.futures as cf
import json
import multiprocessing as mp
import time
import webbrowser
from contextlib import contextmanager
from functools import partial
from typing import Annotated
from urllib import request

import networkx as nx
import uvicorn
from fastapi import FastAPI, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from networkx.readwrite import json_graph

# TODO:
# - Re-split-out the api and opener; don't hide the fact that it's a web app.
# - Then, have the "opener" handle syncing the file locally
# - Good UX for opening + using:
#   - Demonstrate easy opening from vim
#   - Sync to reasonably-named image like I do with my vim autocmd
#   - Allow hidden server-running, or running server beforehand
#   - Figure out how to get and use executable in path
#   - Figure out what to do about opening multiple files in different dirs
#     (because rn the api is run in a dir)
# - Host a demo
# - Put it out there
# ---------------------------
# - Edit edges
# - Edit nodes and edges in normal DOT format instead of json
# - Allow preserving URL and color attributes
# - Better output indentation

# Note, opening from vim:
# silent ! BROWSER=firefox python3 ./src/dgraphack/main.py --reload --file=% > /dev/null 2>&1 &


API_PORT = 8123
API_URL = f"http://localhost:{API_PORT}"

# Monkey-patch StaticFiles so it never caches the images, because they change quickly.
StaticFiles.is_not_modified = lambda self, *args, **kwargs: False


app = FastAPI()
app.mount("/imgs", StaticFiles(directory="./"))

print = partial(print, flush=True)


def print_dot(graph):
	nx.nx_pydot.write_dot(graph, "/dev/tty")


def print_json(json_data):
	print(json.dumps(json_data, indent=4))


@contextmanager
def mutate_dot_as_json(infile: str, write_output: bool = True):
	dot_graph_in = nx.nx_pydot.read_dot(infile)
	json_data = json_graph.node_link_data(dot_graph_in, edges="edges")
	try:
		yield json_data
	finally:
		if not write_output:
			return
		# TODO: Can we output it with proper indentation?
		graph_out = json_graph.node_link_graph(json_data, edges="edges")
		nx.nx_pydot.write_dot(graph_out, infile)


@app.get("/", response_class=HTMLResponse)
async def root(
	infile: str,
	sel_node: Annotated[list[str] | None, Query()] = None,
):
	with mutate_dot_as_json(infile, write_output=False) as json_data:
		sel_node_set = set(sel_node if sel_node is not None else [])
		selected_nodes_args = "".join([f"&sel_node={id}" for id in sel_node_set])

		for n in json_data["nodes"]:
			n["URL"] = f"{API_URL}/selectnode?infile={infile}{selected_nodes_args}&id={n["id"]}"
			if n["id"] in sel_node_set:
				n["color"] = "red"
		for e in json_data["edges"]:
			e["URL"] = f"{API_URL}/selectedge?infile={infile}{selected_nodes_args}&source={e["source"]}&target={e["target"]}"

		graph_out = json_graph.node_link_graph(json_data, edges="edges")
		pydot_graph = nx.drawing.nx_pydot.to_pydot(graph_out)
		pydot_graph.write_svg("graphout.svg")
		pydot_graph.write_cmapx("graphout.cmapx")
		with open("graphout.cmapx", 'r') as file:
			cmapx_content = file.read()

	delete_html_form = "" if len(sel_node_set) == 0 else f"""
	<form action="/deletenode" method="post">
		<strong>Delete Node</strong><br>
		<input type="hidden" name="id" value="{list(sel_node_set)[0]}">
		<input type="hidden" name="infile" value="{infile}" />
		<input type="submit" value="Submit">
	</form>
	"""

	edit_html_form = ""
	if len(sel_node_set) != 0:
		node_data = [n for n in json_data["nodes"] if n["id"] == list(sel_node_set)[0]][0]
		node_data_pruned_json = json.dumps(
			{k:v for k,v in node_data.items() if k not in ["id", "URL", "color"]},
			indent=4
		)
		edit_html_form = f"""
		<form action="/editnode" method="post" id="editnodeform">
			<strong>Edit Node</strong><br>
			<label for="edit_node_data">Node Data (json):</label><br>
			<textarea name="edit_node_data" cols="25" rows="3" form="editnodeform">{node_data_pruned_json}</textarea><br>
			<label for="new_id">Id:</label>
			<input type="text" id="new_id" name="new_id" style="width: 75px" value="{list(sel_node_set)[0]}"><br>
			<input type="hidden" name="id" value="{list(sel_node_set)[0]}">
			<input type="hidden" name="infile" value="{infile}"/>
			<input type="submit" value="Submit">
		</form>
		"""

	return f"""
	<html>
		<body>
			<div style="float: left; width: 50%">
				<img src="imgs/graphout.svg" usemap="#G" alt="graph" />
				{cmapx_content}
			</div>
			<div style="float: right; width: 22%">
				<form action="/addnode" method="post">
					<strong>Add Node</strong><br>
					<label for="id">Id:</label>
					<input type="text" id="id" name="id" style="width: 75px" value=""><br>
					<input type="hidden" name="infile" value="{infile}" />
					<input type="submit" value="Submit">
				</form>
				{delete_html_form}
				{edit_html_form}
			</div>
		</body>
	</html>
	"""


@app.get("/selectnode/")
async def select_node(
	infile: str,
	id: str,
	sel_node: Annotated[list[str] | None, Query()] = None,
):
	sel_node_set = set(sel_node if sel_node is not None else [])

	if id in sel_node_set:
		sel_node_set.remove(id)
	elif len(sel_node_set) == 0:
		sel_node_set.add(id)
	else:
		with mutate_dot_as_json(infile) as json_data:
			json_data["edges"] = [
				dict([(k,v) for k,v in e.items() if k != "key"])
				for e in json_data["edges"]
			]
			json_data["edges"].append({
				"source": list(sel_node_set)[0],
				"target": id,
			})
		sel_node_set.clear()

	selected_nodes_args = "".join([f"&sel_node={id}" for id in sel_node_set])
	return RedirectResponse(f"{API_URL}/?infile={infile}{selected_nodes_args}")


@app.get("/selectedge/")
async def select_edge(
	infile: str,
	source: str,
	target: str,
):
	with mutate_dot_as_json(infile) as json_data:
		json_data["edges"] = [
			e for e in json_data["edges"]
			if not (e["source"] == source and e["target"] == target)
		]
	return RedirectResponse(f"{API_URL}/?infile={infile}")


@app.post("/addnode/")
async def add_node(
	infile: Annotated[str, Form()],
	id: Annotated[str, Form()],
):
	with mutate_dot_as_json(infile) as json_data:
		json_data["nodes"].append({
			"id": id,
		})
	return RedirectResponse(f"{API_URL}/?infile={infile}", status_code=303)


@app.post("/deletenode/")
async def delete_node(
	infile: Annotated[str, Form()],
	id: Annotated[str, Form()],
):
	with mutate_dot_as_json(infile) as json_data:
		json_data["nodes"] = [
			n for n in json_data["nodes"]
			if n["id"] != id
		]
		json_data["edges"] = [
			e for e in json_data["edges"]
			if id not in [e["source"], e["target"]]
		]
	return RedirectResponse(f"{API_URL}/?infile={infile}", status_code=303)


@app.post("/editnode/")
async def edit_node(
	infile: Annotated[str, Form()],
	id: Annotated[str, Form()],
	new_id: Annotated[str, Form()],
	edit_node_data: Annotated[str, Form()],
):
	edit_node_data_json = json.loads(edit_node_data)
	with mutate_dot_as_json(infile) as json_data:
		for n in json_data["nodes"]:
			if n["id"] == id:
				n.clear()
				n.update(edit_node_data_json)
				n["id"] = new_id
				break
		for e in json_data["edges"]:
			if e["source"] == id:
				e["source"] = new_id
			if e["target"] == id:
				e["target"] = new_id
	return RedirectResponse(f"{API_URL}/?infile={infile}", status_code=303)


# TODO: Don't require file just to run or request the api

def api_is_running(dot_file: str) -> bool:
	req =  request.Request(f"{API_URL}/?infile={dot_file}")
	try:
		request.urlopen(req, timeout=0.5)
	except Exception:
		return False
	return True


def ensure_api_is_running(reload: bool, dot_file: str):
	# The api can be started seperately, beforehand.
	if api_is_running(dot_file):
		return
	uvicorn.run("main:app", host="0.0.0.0", port=API_PORT, reload=reload)


def open_app_in_browser(dot_file: str):
	# Poll the api to make sure it exists, before opening browser.
	while not api_is_running(dot_file):
		time.sleep(0.1)
	webbrowser.open(f"{API_URL}/?infile={dot_file}")


async def _main(executor, args):
	loop = asyncio.get_running_loop()
	run = partial(loop.run_in_executor, executor)

	api_fut = run(ensure_api_is_running, args.reload, args.file),

	if not args.run_api_only:
		open_app_in_browser(args.file)

	for fut in api_fut:
		await fut


if __name__ == "__main__":
	import argparse
	arg_parser = argparse.ArgumentParser(exit_on_error=True)
	arg_parser.add_argument("--reload", action='store_true')
	arg_parser.add_argument("--run-api-only", action='store_true')
	arg_parser.add_argument("--file", "-f", type=str, required=True)
	args = arg_parser.parse_args()

	mp.set_start_method("spawn")
	with cf.ProcessPoolExecutor(max_workers=2) as executor:
		asyncio.run(_main(executor, args))

