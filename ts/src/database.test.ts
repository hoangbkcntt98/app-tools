import assert from "node:assert/strict";
import test from "node:test";

import { createDatabasePool } from "./database.js";

test("PostgreSQL CRUD uses quoted identifiers and parameterized values", async () => {
  const calls: Array<{ sql: string; values: unknown[] }> = [];
  const pool = {
    query: async (sql: string, values: unknown[]) => {
      calls.push({ sql, values });
      return { rows: [{ id: 2, name: "new" }] };
    },
    end: async () => {},
  };
  const db = await createDatabasePool({
    settings: { driver: "postgresql" },
    pool,
  });

  const inserted = await db.insert("public.people", { name: "new" });
  assert.deepEqual(inserted, { id: 2, name: "new" });
  assert.equal(calls[0].sql, 'INSERT INTO "public"."people" ("name") VALUES ($1) RETURNING *');
  assert.deepEqual(calls[0].values, ["new"]);

  await db.update("people", { name: "updated" }, { id: 2 });
  assert.equal(calls[1].sql, 'UPDATE "people" SET "name" = $1 WHERE "id" = $2 RETURNING *');
  assert.deepEqual(calls[1].values, ["updated", 2]);

  await db.delete("people", { id: 2 });
  assert.equal(calls[2].sql, 'DELETE FROM "people" WHERE "id" = $1 RETURNING *');
});

test("CRUD rejects unsafe identifiers and unbounded deletes", async () => {
  const db = await createDatabasePool({
    settings: { driver: "mysql" },
    pool: { execute: async () => [{ affectedRows: 1 }], end: async () => {} },
  });
  await assert.rejects(db.select("people; DROP TABLE people"), /invalid SQL identifier/);
  await assert.rejects(db.delete("people", {}), /where must not be empty/);
});
