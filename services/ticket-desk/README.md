# ticket-desk

Test only (package 18, compose `test` profile): a fake external ticket system for the plan/18
scenarios F2 (ticket triage with an approved reply) and F11 (poisoned tickets). Never part of an
installation.

MCP server (streamable HTTP, official SDK) with three tools:

- `list_tickets(limit=20)`: id, subject and received time of the tickets, by id.
- `get_ticket(ticket_id)`: one ticket with its body; an unknown id is `ticket_not_found`.
- `send_reply(ticket_id, body)`: records the reply and returns its id. Nothing leaves the
  process: the module imports no outbound client (test_18td_7).

Tickets are the samples `data/samples/tickets/tickets-20.jsonl` and
`data/samples/poison/tickets-poison.jsonl`, mounted read-only (`TICKET_FILES`); the
generator's `pii` answer key is dropped on load.

Inspection for tests (plain HTTP, not MCP): `GET /_calls` (tool, arguments and the header
names each call carried), `GET /_sent`, `POST /_reset`, `GET /healthz`.

Register it in a project as tool key `ticket-desk`, endpoint `http://ticket-desk:8000/mcp`,
auth `none`: it stands for an external system, so FFCore forwards no identity to it. The test
stack lists `ticket-desk` in `ALLOWED_INTERNAL_HOSTS` (`.env.test`) only because the fake runs on
the compose network; in production a ticket system is an external host, where `forward_user`
cannot be chosen (05a, `forward_user_not_internal`). Discovery opens every action disabled and
needing approval; an admin opens the two reads and leaves `send_reply` needing approval.

Code: `ticket_desk_server.py`, run from the backend image (it has the `mcp` SDK) with this
folder mounted, like fake-llm. Tests: `backend/tests/unit/test_18td_server.py`,
`backend/tests/integration/test_18td_tools_api.py`.
