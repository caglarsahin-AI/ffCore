import { test } from "@playwright/test";

// Brief 10 kabul 2: an action that needs approval shows an inline prompt in the test panel and the
// run continues after the decision (07 approve|reject, D1); a rejection reaches the model.
// NOT_RUN: fake-llm cannot call a tool yet, so no approval is ever requested on the e2e stack.
// The test worker adds a `tool-*` mode in fix/fake-llm-tool-mode (K-10bp2-0004); after that merge
// this test is written against ticket-desk send_reply (needs approval) and the fixme is removed.
test.fixme("test_10bp2_5_inline_approval: NOT_RUN until fix/fake-llm-tool-mode (K-10bp2-0004)", async () => {});
