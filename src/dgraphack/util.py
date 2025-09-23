import json
import os
from contextlib import contextmanager

import networkx as nx
from networkx.readwrite import json_graph

from dgraphack.consts import API_WORK_DIR


def get_file_link_path(sessionid: str):
	return os.path.join(API_WORK_DIR, sessionid, "filelink.dot")


def get_dot_as_json(sessionid: str):
	workspace_file_path = get_file_link_path(sessionid)
	dot_graph_in = nx.nx_pydot.read_dot(workspace_file_path)
	return json_graph.node_link_data(dot_graph_in, edges="edges")


@contextmanager
def mutate_dot_as_json(sessionid: str):
	json_data = get_dot_as_json(sessionid)

	# Let the caller have the JSON data to mutate it.
	yield json_data

	# Now that we're back, reconvert the JSON back to a graph, and write it out.
	graph_out = json_graph.node_link_graph(json_data, edges="edges")
	pydot_graph = nx.drawing.nx_pydot.to_pydot(graph_out)

	with open(get_file_link_path(sessionid), "w") as dot_out_file:
		dot_out_file.write(
			pydot_graph.to_string(indent="    "),
		)


def get_pruned_json_node_data(json_data: dict, node_id: str):
	node_data = [n for n in json_data["nodes"] if n["id"] == node_id][0]
	return json.dumps(
		{k:v for k,v in node_data.items() if k not in ["id", "URL", "color"]},
		indent=4
	)

