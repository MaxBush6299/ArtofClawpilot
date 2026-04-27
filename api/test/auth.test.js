import assert from "node:assert/strict";
import { validateApiKey } from "../src/lib/auth.js";

const missingHeaderRequest = {
  headers: {
    get() {
      return undefined;
    },
  },
};

assert.equal(await validateApiKey(missingHeaderRequest), false);

console.log("PASS auth.test.js");
