import { test } from "@playwright/test";

// Sign in, create a project, see it in the list. Needs the request/response bodies of
// POST /auth/login and POST /projects from the 03a OpenAPI contract, which does not exist yet.
// Coordinator decision K-10a-0002 (A): fixme here, enabled in 10a-binding. NOT_RUN in the PR.
test.fixme("test_10a_7_login_project_flow: sign in and create a project", async () => {});
