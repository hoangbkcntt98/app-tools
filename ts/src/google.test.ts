import assert from "node:assert/strict";
import test from "node:test";

import { readSpreadsheet, writeSpreadsheet } from "./google.js";

test("blank Sheets options fall back to valid API defaults", async () => {
  let readOptions: Record<string, any> | undefined;
  let writeOptions: Record<string, any> | undefined;
  const service = {
    spreadsheets: {
      get: async () => ({
        data: { properties: { title: "Test" }, sheets: [] },
      }),
      values: {
        get: async (options: Record<string, any>) => {
          readOptions = options;
          return { data: { range: options.range, values: [["hello"]] } };
        },
        update: async (options: Record<string, any>) => {
          writeOptions = options;
          return { data: { updatedCells: 1 } };
        },
      },
    },
  };

  await readSpreadsheet("sheet-id", {
    ranges: ["Sheet1!A1"],
    config: { google: { value_render_option: "" } },
    service,
  });
  await writeSpreadsheet("sheet-id", "Sheet1!A1", [["hello"]], {
    config: { google: { value_input_option: "" } },
    service,
  });

  assert.equal(readOptions?.valueRenderOption, "FORMATTED_VALUE");
  assert.equal(writeOptions?.valueInputOption, "USER_ENTERED");
});
