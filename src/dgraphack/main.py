#!/usr/bin/env python3

import json
from functools import partial
from typing import Annotated

import networkx as nx
import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from networkx.readwrite import json_graph


# TODO:
# - Clean and refactor
# - Edit everything else about a node
# - Good UX for opening + using:
#   - Demonstrate easy opening from vim
#   - Sync to reasonably-named image like I do with my vim autocmd
#   - Allow hidden server-running, or running server beforehand
# - Better output indentation
# - Host a demo
# - Put it out there


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


@app.get("/", response_class=HTMLResponse)
async def root(infile: str, sn: Annotated[list[str] | None, Query()] = None):
	dot_graph_in = nx.nx_pydot.read_dot(infile)

	json_data = json_graph.node_link_data(dot_graph_in, edges="edges")
	sn_set = set(sn if sn is not None else [])
	selected_nodes_args = "".join([f"&sn={id}" for id in sn_set])

	for n in json_data["nodes"]:
		n["URL"] = f"{API_URL}/selectnode?infile={infile}{selected_nodes_args}&id={n["id"]}"
		if n["id"] in sn_set:
			n["color"] = "red"
	for e in json_data["edges"]:
		e["URL"] = f"{API_URL}/selectedge?infile={infile}{selected_nodes_args}&source={e["source"]}&target={e["target"]}"

	graph_out = json_graph.node_link_graph(json_data, edges="edges")
	# TODO: Can we output it with proper indentation?
	nx.nx_pydot.write_dot(graph_out, "graphout.dot")

	pydot_graph = nx.drawing.nx_pydot.to_pydot(graph_out)
	pydot_graph.write_svg("graphout.svg")
	pydot_graph.write_cmapx("graphout.cmapx")
	with open("graphout.cmapx", 'r') as file:
		cmapx_content = file.read()

	delete_html_form = "" if len(sn_set) == 0 else f"""
	<form action="/deletenode">
		<strong>Delete Node</strong>
		<input type="hidden" name="id" value="{list(sn_set)[0]}">
		<input type="hidden" name="infile" value="{infile}" />
		<input type="submit" value="Submit">
	</form>
	"""

	edit_html_form = "" if len(sn_set) == 0 else f"""
	<form action="/editnode">
		<strong>Edit Node</strong><br>
		<label for="new_id">New Id:</label>
		<input type="text" id="new_id" name="new_id" style="width: 75px" value="{list(sn_set)[0]}"><br>
		<input type="hidden" name="id" value="{list(sn_set)[0]}">
		<input type="hidden" name="infile" value="{infile}" />
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
			<div style="float: right; width: 15%">
				<form action="/addnode">
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
async def select_node(infile: str, id: str, sn: Annotated[list[str] | None, Query()] = None):
	sn_set = set(sn if sn is not None else [])

	if id in sn_set:
		sn_set.remove(id)
	elif len(sn_set) == 0:
		sn_set.add(id)
	else:
		dot_graph_in = nx.nx_pydot.read_dot(infile)
		json_data = json_graph.node_link_data(dot_graph_in, edges="edges")
		json_data["edges"] = [
			dict([(k,v) for k,v in e.items() if k != "key"])
			for e in json_data["edges"]
		]
		json_data["edges"].append({
			"source": list(sn_set)[0],
			"target": id,
		})

		graph_out = json_graph.node_link_graph(json_data, edges="edges")
		nx.nx_pydot.write_dot(graph_out, infile)
		sn_set.clear()

	selected_nodes_args = "".join([f"&sn={id}" for id in sn_set])
	return RedirectResponse(f"{API_URL}/?infile={infile}{selected_nodes_args}")


@app.get("/selectedge/")
async def select_edge(infile: str, source: str, target: str):
	dot_graph_in = nx.nx_pydot.read_dot(infile)
	json_data = json_graph.node_link_data(dot_graph_in, edges="edges")
	json_data["edges"] = [
		e for e in json_data["edges"]
		if not (e["source"] == source and e["target"] == target)
	]
	graph_out = json_graph.node_link_graph(json_data, edges="edges")
	nx.nx_pydot.write_dot(graph_out, infile)
	return RedirectResponse(f"{API_URL}/?infile={infile}")


@app.get("/addnode/")
async def add_node(infile: str, id: str):
	dot_graph_in = nx.nx_pydot.read_dot(infile)
	json_data = json_graph.node_link_data(dot_graph_in, edges="edges")

	json_data["nodes"].append({
		"id": id,
	})

	graph_out = json_graph.node_link_graph(json_data, edges="edges")
	nx.nx_pydot.write_dot(graph_out, infile)
	return RedirectResponse(f"{API_URL}/?infile={infile}")


@app.get("/deletenode/")
async def delete_node(infile: str, id: str):
	dot_graph_in = nx.nx_pydot.read_dot(infile)
	json_data = json_graph.node_link_data(dot_graph_in, edges="edges")

	json_data["nodes"] = [
		n for n in json_data["nodes"]
		if n["id"] != id
	]
	json_data["edges"] = [
		e for e in json_data["edges"]
		if id not in [e["source"], e["target"]]
	]

	graph_out = json_graph.node_link_graph(json_data, edges="edges")
	nx.nx_pydot.write_dot(graph_out, infile)
	return RedirectResponse(f"{API_URL}/?infile={infile}")


@app.get("/editnode/")
async def edit_node(infile: str, id: str, new_id: str):
	dot_graph_in = nx.nx_pydot.read_dot(infile)
	json_data = json_graph.node_link_data(dot_graph_in, edges="edges")

	for n in json_data["nodes"]:
		if n["id"] == id:
			n["id"] = new_id
	for e in json_data["edges"]:
		if e["source"] == id:
			e["source"] = new_id
		if e["target"] == id:
			e["target"] = new_id

	graph_out = json_graph.node_link_graph(json_data, edges="edges")
	nx.nx_pydot.write_dot(graph_out, infile)
	return RedirectResponse(f"{API_URL}/?infile={infile}")


if __name__ == "__main__":
	import argparse
	arg_parser = argparse.ArgumentParser(exit_on_error=True)
	arg_parser.add_argument("--reload", action='store_true')
	args = arg_parser.parse_args()

	uvicorn.run("main:app", host="0.0.0.0", port=API_PORT, reload=args.reload)

