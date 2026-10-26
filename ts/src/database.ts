import { type ConfigInput, sectionConfig } from "./config.js";

type Driver = "postgresql" | "mysql";

function quoteIdentifier(value: string, driver: Driver): string {
  const parts = value.split(".");
  if (!parts.length || parts.some((part) => !/^[A-Za-z_][A-Za-z0-9_$]*$/.test(part))) {
    throw new TypeError(`invalid SQL identifier: ${value}`);
  }
  const quote = driver === "mysql" ? "`" : '"';
  return parts.map((part) => `${quote}${part}${quote}`).join(".");
}

function whereClause(
  where: Record<string, unknown>,
  values: unknown[],
  driver: Driver,
): string {
  const entries = Object.entries(where);
  if (!entries.length) throw new TypeError("where must not be empty");
  return entries.map(([key, value]) => {
    const column = quoteIdentifier(key, driver);
    if (value === null) return `${column} IS NULL`;
    values.push(value);
    return `${column} = ${driver === "postgresql" ? `$${values.length}` : "?"}`;
  }).join(" AND ");
}

export class DatabasePool {
  private constructor(
    private readonly pool: any,
    private readonly driver: Driver,
  ) {}

  static async create(options: {
    config?: ConfigInput;
    settings?: Record<string, any>;
    pool?: any;
  } = {}): Promise<DatabasePool> {
    const settings = options.settings ?? await sectionConfig(options.config, "database");
    const selected = String(settings.driver ?? "").toLowerCase();
    const driver: Driver = ["postgres", "postgresql", "psql"].includes(selected)
      ? "postgresql"
      : selected === "mysql"
      ? "mysql"
      : (() => {
        throw new TypeError("database.driver must be 'postgresql' or 'mysql'");
      })();
    if (options.pool) return new DatabasePool(options.pool, driver);

    if (driver === "postgresql") {
      const { Pool } = await import("pg");
      const { driver: _driver, ...config } = settings;
      return new DatabasePool(new Pool(config), driver);
    }
    const mysql = await import("mysql2/promise");
    const { driver: _driver, ...config } = settings;
    return new DatabasePool(mysql.createPool(config), driver);
  }

  async select(
    table: string,
    options: {
      where?: Record<string, unknown>;
      columns?: string[];
      limit?: number;
    } = {},
  ): Promise<Record<string, any>[]> {
    const selected = options.columns?.length
      ? options.columns.map((column) => quoteIdentifier(column, this.driver)).join(", ")
      : "*";
    const values: unknown[] = [];
    let sql = `SELECT ${selected} FROM ${quoteIdentifier(table, this.driver)}`;
    if (options.where) {
      sql += ` WHERE ${whereClause(options.where, values, this.driver)}`;
    }
    if (options.limit !== undefined) {
      if (!Number.isInteger(options.limit) || options.limit < 1) {
        throw new TypeError("limit must be a positive integer");
      }
      values.push(options.limit);
      sql += ` LIMIT ${this.driver === "postgresql" ? `$${values.length}` : "?"}`;
    }
    const result = await this.run(sql, values);
    return this.driver === "postgresql" ? result.rows : result;
  }

  async insert(table: string, values: Record<string, unknown>): Promise<any> {
    const columns = Object.keys(values);
    if (!columns.length) throw new TypeError("values must not be empty");
    const quotedColumns = columns.map((column) => quoteIdentifier(column, this.driver));
    const placeholders = columns.map((_, index) =>
      this.driver === "postgresql" ? `$${index + 1}` : "?",
    );
    let sql = `INSERT INTO ${quoteIdentifier(table, this.driver)} (${quotedColumns.join(", ")}) VALUES (${placeholders.join(", ")})`;
    if (this.driver === "postgresql") sql += " RETURNING *";
    const result = await this.run(sql, Object.values(values));
    return this.driver === "postgresql" ? result.rows[0] : result;
  }

  async update(
    table: string,
    values: Record<string, unknown>,
    where: Record<string, unknown>,
  ): Promise<any> {
    const columns = Object.keys(values);
    if (!columns.length) throw new TypeError("values must not be empty");
    const params: unknown[] = Object.values(values);
    const assignments = columns.map((column, index) =>
      `${quoteIdentifier(column, this.driver)} = ${this.driver === "postgresql" ? `$${index + 1}` : "?"}`,
    );
    const clause = whereClause(where, params, this.driver);
    if (this.driver === "postgresql") {
      const result = await this.run(
        `UPDATE ${quoteIdentifier(table, this.driver)} SET ${assignments.join(", ")} WHERE ${clause} RETURNING *`,
        params,
      );
      return result.rows;
    }
    return this.run(
      `UPDATE ${quoteIdentifier(table, this.driver)} SET ${assignments.join(", ")} WHERE ${clause}`,
      params,
    );
  }

  async delete(table: string, where: Record<string, unknown>): Promise<any> {
    const params: unknown[] = [];
    const clause = whereClause(where, params, this.driver);
    const sql = this.driver === "postgresql"
      ? `DELETE FROM ${quoteIdentifier(table, this.driver)} WHERE ${clause} RETURNING *`
      : `DELETE FROM ${quoteIdentifier(table, this.driver)} WHERE ${clause}`;
    const result = await this.run(sql, params);
    return this.driver === "postgresql" ? result.rows : result;
  }

  async close(): Promise<void> {
    if (this.driver === "postgresql") await this.pool.end();
    else await this.pool.end();
  }

  private async run(sql: string, values: unknown[]): Promise<any> {
    if (this.driver === "postgresql") return this.pool.query(sql, values);
    const [result] = await this.pool.execute(sql, values);
    return result;
  }
}

export async function createDatabasePool(options: {
  config?: ConfigInput;
  settings?: Record<string, any>;
  pool?: any;
} = {}): Promise<DatabasePool> {
  return DatabasePool.create(options);
}
