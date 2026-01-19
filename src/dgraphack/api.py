import io
import json
import os
from functools import partial
from typing import Annotated

import networkx as nx
from fastapi import FastAPI, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from networkx.readwrite import json_graph

from dgraphack.consts import API_URL, API_WORK_DIR
from dgraphack.util import get_dot_as_json, mutate_dot_as_json, get_pruned_json_node_data

# Monkey-patch StaticFiles so it never caches the images, because they change quickly.
StaticFiles.is_not_modified = lambda self, *args, **kwargs: False

for path in [API_WORK_DIR]:
	os.makedirs(path, exist_ok=True)

app = FastAPI()
global_img_store: dict[str, bytes] = dict()

print = partial(print, flush=True)


@app.get("/", response_class=HTMLResponse)
async def root(
	sessionid: str | None = None,
	sel_node: Annotated[list[str] | None, Query()] = None,
):
	if sessionid is None:
		return "Provide sessionid (just run `dgraphack edit <file>`)"

	json_data = get_dot_as_json(sessionid)

	graph_name = json_data["graph"]["name"] \
		if "name" in json_data["graph"] \
		else "%1" # pydot automatically gives this as the name and id for the graph in the cmapx.

	sel_node_set = set(sel_node if sel_node is not None else [])
	selected_nodes_args = "".join([f"&sel_node={id}" for id in sel_node_set])

	for n in json_data["nodes"]:
		n["URL"] = f"{API_URL}/selectnode?sessionid={sessionid}{selected_nodes_args}&id={n["id"]}"
		if n["id"] in sel_node_set:
			n["color"] = "red"
	for e in json_data["edges"]:
		e["URL"] = f"{API_URL}/selectedge?sessionid={sessionid}{selected_nodes_args}&source={e["source"]}&target={e["target"]}"

	graph_out = json_graph.node_link_graph(json_data, edges="edges")
	pydot_graph = nx.drawing.nx_pydot.to_pydot(graph_out)
	cmapx_content = pydot_graph.create_cmapx().decode("utf-8")

	# Cache the image so it can be retrieved by the /imgs endpoint.
	global_img_store[sessionid] = pydot_graph.create_svg()

	add_html_form = f"""
	<form action="/addnode" method="post">
		<strong>Add Node</strong><br>
		<label for="id">Id:</label>
		<input type="text" id="id" name="id" style="width: 75px" value=""><br>
		<input type="hidden" name="sessionid" value="{sessionid}" />
		<input type="submit" value="Submit">
	</form>
	"""

	delete_html_form = "" if len(sel_node_set) == 0 else f"""
	<form action="/deletenode" method="post">
		<strong>Delete Node</strong><br>
		<input type="hidden" name="id" value="{list(sel_node_set)[0]}">
		<input type="hidden" name="sessionid" value="{sessionid}" />
		<input type="submit" value="Submit">
	</form>
	"""

	edit_html_form = "" if len(sel_node_set) == 0 else f"""
	<form action="/editnode" method="post" id="editnodeform">
		<strong>Edit Node</strong><br>
		<label for="edit_node_data">Node Data (json):</label><br>
		<textarea name="edit_node_data" cols="25" rows="3" form="editnodeform">""" + \
			get_pruned_json_node_data(json_data, list(sel_node_set)[0]) + \
		f"""</textarea><br>
		<label for="new_id">Id:</label>
		<input type="text" id="new_id" name="new_id" style="width: 75px" value="{list(sel_node_set)[0]}"><br>
		<input type="hidden" name="id" value="{list(sel_node_set)[0]}">
		<input type="hidden" name="sessionid" value="{sessionid}"/>
		<input type="submit" value="Submit">
	</form>
	"""

	return f"""
	<!DOCTYPE html>
	<html>
		<head>
			<style>
				.graphimg {{
					display: block;
					margin-left: auto;
				}}
			</style>
		</head>
		<body>
			<div style="float: left; width: 50%">
				<img src="imgs/{sessionid}" usemap="#{graph_name}" alt="graph {graph_name}" class="graphimg"/>
				{cmapx_content}
			</div>
			<div style="float: right; width: 22%">
				{add_html_form}<br>
				{delete_html_form}<br>
				{edit_html_form}<br>
			</div>
		</body>
	</html>
	"""


@app.get(
	"/imgs/{sessionid}",
	response_class=StreamingResponse,
	responses= {200: {"content": {"image/svg+xml": {}}}},
)
async def get_img(
	sessionid: str,
):
	return StreamingResponse(
		content=io.BytesIO(global_img_store[sessionid]),
		media_type="image/svg+xml",
	)


@app.get("/selectnode/")
async def select_node(
	sessionid: str,
	id: str,
	sel_node: Annotated[list[str] | None, Query()] = None,
):
	sel_node_set = set(sel_node if sel_node is not None else [])

	if id in sel_node_set:
		sel_node_set.remove(id)
	elif len(sel_node_set) == 0:
		sel_node_set.add(id)
	else:
		with mutate_dot_as_json(sessionid) as json_data:
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
	return RedirectResponse(f"{API_URL}/?sessionid={sessionid}{selected_nodes_args}")


@app.get("/selectedge/")
async def select_edge(
	sessionid: str,
	source: str,
	target: str,
):
	with mutate_dot_as_json(sessionid) as json_data:
		json_data["edges"] = [
			e for e in json_data["edges"]
			if not (e["source"] == source and e["target"] == target)
		]
	return RedirectResponse(f"{API_URL}/?sessionid={sessionid}")


@app.post("/addnode/")
async def add_node(
	sessionid: Annotated[str, Form()],
	id: Annotated[str, Form()],
):
	with mutate_dot_as_json(sessionid) as json_data:
		json_data["nodes"].append({
			"id": id,
		})
	return RedirectResponse(f"{API_URL}/?sessionid={sessionid}", status_code=303)


@app.post("/deletenode/")
async def delete_node(
	sessionid: Annotated[str, Form()],
	id: Annotated[str, Form()],
):
	with mutate_dot_as_json(sessionid) as json_data:
		json_data["nodes"] = [
			n for n in json_data["nodes"]
			if n["id"] != id
		]
		json_data["edges"] = [
			e for e in json_data["edges"]
			if id not in [e["source"], e["target"]]
		]
	return RedirectResponse(f"{API_URL}/?sessionid={sessionid}", status_code=303)


@app.post("/editnode/")
async def edit_node(
	sessionid: Annotated[str, Form()],
	id: Annotated[str, Form()],
	new_id: Annotated[str, Form()],
	edit_node_data: Annotated[str, Form()],
):
	edit_node_data_json = json.loads(edit_node_data)
	with mutate_dot_as_json(sessionid) as json_data:
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
	return RedirectResponse(f"{API_URL}/?sessionid={sessionid}", status_code=303)



