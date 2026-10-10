import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api.js";
import { isLiveRefresh, useLive } from "../../live/LiveContext.jsx";
import { inr, qty, ddmmyyyy } from "../../lib/format.js";
import "../../owner.css";

// Owner master data: add + edit buyers, suppliers, machines, employees, and
// correct a wrong yarn receipt. Judges enter real data here, live.
const TABS = [
  ["buyers", "Buyers"],
  ["suppliers", "Suppliers"],
  ["machines", "Machines"],
  ["employees", "Employees"],
  ["receipts", "Yarn receipts"],
];

const MACHINE_TYPES = ["spinning", "weaving", "dyeing"];

export default function MasterData() {
  const [tab, setTab] = useState("buyers");
  return (
    <div className="module owner-page">
      <h2>Master data</h2>
      <p className="muted">
        Add and correct the records the mill runs on. Changes show up live on
        the other screens.
      </p>
      <section className="panel">
        <div className="tabs">
          {TABS.map(([k, label]) => (
            <button
              key={k}
              className={`tab ${tab === k ? "active" : ""}`}
              onClick={() => setTab(k)}
            >
              {label}
            </button>
          ))}
        </div>
        {tab === "buyers" && <Buyers />}
        {tab === "suppliers" && <Suppliers />}
        {tab === "machines" && <Machines />}
        {tab === "employees" && <Employees />}
        {tab === "receipts" && <Receipts />}
      </section>
    </div>
  );
}

/* ---------- a small reusable CRUD section ---------- */
function useRows(path, topics) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  async function load() {
    if (!isLiveRefresh()) setLoading(true);
    setError("");
    try {
      setRows(await apiFetch(path));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useLive(topics, load);
  return { rows, loading, error, reload: load, setError };
}

function Field({ label, children, error, hint }) {
  return (
    <label className="field">
      <span>
        {label} {hint && <small className="muted">{hint}</small>}
      </span>
      {children}
      {error && <small className="field-error">{error}</small>}
    </label>
  );
}

/* ---------- Buyers ---------- */
function Buyers() {
  const { rows, loading, error, reload } = useRows("/api/master/buyers", [
    "orders",
  ]);
  const [editing, setEditing] = useState(null);
  return (
    <>
      <Toolbar
        title="Buyers"
        count={rows.length}
        onAdd={() => setEditing({})}
      />
      {error && <div className="form-error">{error}</div>}
      {loading ? (
        <p className="muted">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="muted">No buyers yet. Add the first one.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Contact</th>
              <th>Phone</th>
              <th>Email</th>
              <th className="num">Credit limit</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((b) => (
              <tr key={b.id}>
                <td>{b.name}</td>
                <td>{b.contact_person || "—"}</td>
                <td>{b.phone || "—"}</td>
                <td>{b.email || "—"}</td>
                <td className="num owner-num">{inr(b.credit_limit)}</td>
                <td className="row-actions">
                  <button className="link-btn" onClick={() => setEditing(b)}>
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {editing && (
        <BuyerForm
          row={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            reload();
          }}
        />
      )}
    </>
  );
}

function BuyerForm({ row, onClose, onSaved }) {
  const isEdit = !!row.id;
  const [f, setF] = useState({
    name: row.name || "",
    contact_person: row.contact_person || "",
    phone: row.phone || "",
    email: row.email || "",
    address: row.address || "",
    credit_limit: row.credit_limit ?? "",
  });
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    if (f.name.trim().length < 2) return setErr("Enter the buyer's name.");
    setSaving(true);
    setErr("");
    try {
      await apiFetch(
        isEdit ? `/api/master/buyers/${row.id}` : "/api/master/buyers",
        {
          method: isEdit ? "PUT" : "POST",
          body: {
            name: f.name.trim(),
            contact_person: f.contact_person.trim() || null,
            phone: f.phone.trim() || null,
            email: f.email.trim() || null,
            address: f.address.trim() || null,
            credit_limit: Number(f.credit_limit) || 0,
          },
        },
      );
      onSaved();
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title={isEdit ? "Edit buyer" : "Add buyer"} onClose={onClose}>
      <form onSubmit={submit} noValidate>
        {err && <div className="form-error">{err}</div>}
        <Field label="Name">
          <input value={f.name} onChange={set("name")} autoFocus />
        </Field>
        <Field label="Contact person" hint="(optional)">
          <input value={f.contact_person} onChange={set("contact_person")} />
        </Field>
        <Field label="Phone" hint="(optional)">
          <input value={f.phone} onChange={set("phone")} />
        </Field>
        <Field label="Email" hint="(optional)">
          <input type="email" value={f.email} onChange={set("email")} />
        </Field>
        <Field label="Address" hint="(optional)">
          <input value={f.address} onChange={set("address")} />
        </Field>
        <Field label="Credit limit (₹)">
          <input
            type="number"
            min="0"
            step="any"
            value={f.credit_limit}
            onChange={set("credit_limit")}
          />
        </Field>
        <DialogActions saving={saving} onClose={onClose} isEdit={isEdit} />
      </form>
    </Dialog>
  );
}

/* ---------- Suppliers ---------- */
function Suppliers() {
  const { rows, loading, error, reload } = useRows("/api/master/suppliers", [
    "payments",
  ]);
  const [editing, setEditing] = useState(null);
  return (
    <>
      <Toolbar
        title="Suppliers"
        count={rows.length}
        onAdd={() => setEditing({})}
      />
      {error && <div className="form-error">{error}</div>}
      {loading ? (
        <p className="muted">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="muted">No suppliers yet. Add the first one.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Phone</th>
              <th>Email</th>
              <th>Address</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td>{s.phone || "—"}</td>
                <td>{s.email || "—"}</td>
                <td>{s.address || "—"}</td>
                <td className="row-actions">
                  <button className="link-btn" onClick={() => setEditing(s)}>
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {editing && (
        <SupplierForm
          row={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            reload();
          }}
        />
      )}
    </>
  );
}

function SupplierForm({ row, onClose, onSaved }) {
  const isEdit = !!row.id;
  const [f, setF] = useState({
    name: row.name || "",
    phone: row.phone || "",
    email: row.email || "",
    address: row.address || "",
  });
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    if (f.name.trim().length < 2) return setErr("Enter the supplier's name.");
    setSaving(true);
    setErr("");
    try {
      await apiFetch(
        isEdit ? `/api/master/suppliers/${row.id}` : "/api/master/suppliers",
        {
          method: isEdit ? "PUT" : "POST",
          body: {
            name: f.name.trim(),
            phone: f.phone.trim() || null,
            email: f.email.trim() || null,
            address: f.address.trim() || null,
          },
        },
      );
      onSaved();
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title={isEdit ? "Edit supplier" : "Add supplier"} onClose={onClose}>
      <form onSubmit={submit} noValidate>
        {err && <div className="form-error">{err}</div>}
        <Field label="Name">
          <input value={f.name} onChange={set("name")} autoFocus />
        </Field>
        <Field label="Phone" hint="(optional)">
          <input value={f.phone} onChange={set("phone")} />
        </Field>
        <Field label="Email" hint="(optional)">
          <input type="email" value={f.email} onChange={set("email")} />
        </Field>
        <Field label="Address" hint="(optional)">
          <input value={f.address} onChange={set("address")} />
        </Field>
        <DialogActions saving={saving} onClose={onClose} isEdit={isEdit} />
      </form>
    </Dialog>
  );
}

/* ---------- Machines ---------- */
function Machines() {
  const { rows, loading, error, reload } = useRows("/api/master/machines", [
    "machines",
  ]);
  const [editing, setEditing] = useState(null);
  return (
    <>
      <Toolbar
        title="Machines"
        count={rows.length}
        onAdd={() => setEditing({})}
      />
      {error && <div className="form-error">{error}</div>}
      {loading ? (
        <p className="muted">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="muted">No machines yet. Add the first one.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Status</th>
              <th className="num">Hourly cost</th>
              <th className="num">Power + overhead</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m) => (
              <tr key={m.id}>
                <td>{m.name}</td>
                <td>{m.type}</td>
                <td>{m.current_status}</td>
                <td className="num owner-num">{inr(m.hourly_cost)}</td>
                <td className="num owner-num">{inr(m.power_overhead_cost)}</td>
                <td className="row-actions">
                  <button className="link-btn" onClick={() => setEditing(m)}>
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {editing && (
        <MachineForm
          row={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            reload();
          }}
        />
      )}
    </>
  );
}

function MachineForm({ row, onClose, onSaved }) {
  const isEdit = !!row.id;
  const [f, setF] = useState({
    name: row.name || "",
    type: row.type || "spinning",
    hourly_cost: row.hourly_cost ?? "",
    power_overhead_cost: row.power_overhead_cost ?? "",
  });
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    if (f.name.trim().length < 2) return setErr("Enter the machine name.");
    const hourly = Number(f.hourly_cost);
    const power = Number(f.power_overhead_cost) || 0;
    if (!(hourly >= 0)) return setErr("Hourly cost must be 0 or more.");
    if (power > hourly)
      return setErr("Power + overhead cannot exceed the full hourly cost.");
    setSaving(true);
    setErr("");
    try {
      await apiFetch(
        isEdit ? `/api/master/machines/${row.id}` : "/api/master/machines",
        {
          method: isEdit ? "PUT" : "POST",
          body: {
            name: f.name.trim(),
            type: f.type,
            hourly_cost: hourly,
            power_overhead_cost: power,
          },
        },
      );
      onSaved();
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title={isEdit ? "Edit machine" : "Add machine"} onClose={onClose}>
      <form onSubmit={submit} noValidate>
        {err && <div className="form-error">{err}</div>}
        <Field label="Name">
          <input value={f.name} onChange={set("name")} autoFocus />
        </Field>
        <Field label="Type">
          <select value={f.type} onChange={set("type")}>
            {MACHINE_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </Field>
        <Field
          label="Hourly cost (₹/hr)"
          hint="power + overhead + operator wage"
        >
          <input
            type="number"
            min="0"
            step="any"
            value={f.hourly_cost}
            onChange={set("hourly_cost")}
          />
        </Field>
        <Field
          label="Power + overhead (₹/hr)"
          hint="no wages — used for cost per order"
        >
          <input
            type="number"
            min="0"
            step="any"
            value={f.power_overhead_cost}
            onChange={set("power_overhead_cost")}
          />
        </Field>
        <DialogActions saving={saving} onClose={onClose} isEdit={isEdit} />
      </form>
    </Dialog>
  );
}

/* ---------- Employees ---------- */
function Employees() {
  const { rows, loading, error, reload } = useRows("/api/master/employees", [
    "wages",
  ]);
  const [editing, setEditing] = useState(null);
  return (
    <>
      <Toolbar
        title="Employees"
        count={rows.length}
        onAdd={() => setEditing({})}
      />
      {error && <div className="form-error">{error}</div>}
      {loading ? (
        <p className="muted">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="muted">No employees yet. Add the first one.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Role on floor</th>
              <th className="num">Daily wage</th>
              <th>Phone</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.id}>
                <td>{e.name}</td>
                <td>{e.role_on_floor || "—"}</td>
                <td className="num owner-num">{inr(e.daily_wage)}</td>
                <td>{e.phone || "—"}</td>
                <td className="row-actions">
                  <button className="link-btn" onClick={() => setEditing(e)}>
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {editing && (
        <EmployeeForm
          row={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            reload();
          }}
        />
      )}
    </>
  );
}

function EmployeeForm({ row, onClose, onSaved }) {
  const isEdit = !!row.id;
  const [f, setF] = useState({
    name: row.name || "",
    role_on_floor: row.role_on_floor || "",
    daily_wage: row.daily_wage ?? "",
    phone: row.phone || "",
  });
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    if (f.name.trim().length < 2) return setErr("Enter the employee's name.");
    if (!(Number(f.daily_wage) >= 0))
      return setErr("Daily wage must be 0 or more.");
    setSaving(true);
    setErr("");
    try {
      await apiFetch(
        isEdit ? `/api/master/employees/${row.id}` : "/api/master/employees",
        {
          method: isEdit ? "PUT" : "POST",
          body: {
            name: f.name.trim(),
            role_on_floor: f.role_on_floor.trim() || null,
            daily_wage: Number(f.daily_wage) || 0,
            phone: f.phone.trim() || null,
          },
        },
      );
      onSaved();
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title={isEdit ? "Edit employee" : "Add employee"} onClose={onClose}>
      <form onSubmit={submit} noValidate>
        {err && <div className="form-error">{err}</div>}
        <Field label="Name">
          <input value={f.name} onChange={set("name")} autoFocus />
        </Field>
        <Field label="Role on floor" hint="(optional)">
          <input value={f.role_on_floor} onChange={set("role_on_floor")} />
        </Field>
        <Field label="Daily wage (₹)">
          <input
            type="number"
            min="0"
            step="any"
            value={f.daily_wage}
            onChange={set("daily_wage")}
          />
        </Field>
        <Field label="Phone" hint="(optional)">
          <input value={f.phone} onChange={set("phone")} />
        </Field>
        <DialogActions saving={saving} onClose={onClose} isEdit={isEdit} />
      </form>
    </Dialog>
  );
}

/* ---------- Yarn receipts (correction only) ---------- */
function Receipts() {
  const { rows, loading, error, reload } = useRows(
    "/api/master/yarn-receipts",
    ["yarn"],
  );
  const [editing, setEditing] = useState(null);
  return (
    <>
      <div className="toolbar">
        <h3>Yarn receipts</h3>
        <span className="muted">{rows.length} total</span>
      </div>
      <p className="muted">
        Correct a wrong quantity, rate or linked order. Stock is adjusted by the
        difference.
      </p>
      {error && <div className="form-error">{error}</div>}
      {loading ? (
        <p className="muted">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="muted">No yarn receipts recorded.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Yarn</th>
              <th>Colour</th>
              <th className="num">Qty</th>
              <th className="num">Rate</th>
              <th>Order</th>
              <th>Supplier</th>
              <th>Received</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.yarn_type}</td>
                <td>{r.colour}</td>
                <td className="num">{qty(r.quantity_kg, "kg")}</td>
                <td className="num owner-num">{inr(r.unit_cost)}</td>
                <td>{r.order_no || "—"}</td>
                <td>{r.supplier_name || "—"}</td>
                <td>{ddmmyyyy(r.received_at)}</td>
                <td className="row-actions">
                  <button className="link-btn" onClick={() => setEditing(r)}>
                    Correct
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {editing && (
        <ReceiptForm
          row={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            reload();
          }}
        />
      )}
    </>
  );
}

function ReceiptForm({ row, onClose, onSaved }) {
  const [f, setF] = useState({
    quantity_kg: row.quantity_kg ?? "",
    unit_cost: row.unit_cost ?? "",
    order_id: row.order_id ?? "",
  });
  const [orders, setOrders] = useState([]);
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  useEffect(() => {
    apiFetch("/api/orders")
      .then(setOrders)
      .catch(() => setOrders([]));
  }, []);

  async function submit(e) {
    e.preventDefault();
    if (!(Number(f.quantity_kg) > 0))
      return setErr("Quantity must be more than 0.");
    setSaving(true);
    setErr("");
    try {
      await apiFetch(`/api/master/yarn-receipts/${row.id}`, {
        method: "PUT",
        body: {
          quantity_kg: Number(f.quantity_kg),
          unit_cost: Number(f.unit_cost) || 0,
          order_id: f.order_id ? Number(f.order_id) : null,
        },
      });
      onSaved();
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      title={`Correct receipt — ${row.yarn_type} (${row.colour})`}
      onClose={onClose}
    >
      <form onSubmit={submit} noValidate>
        {err && <div className="form-error">{err}</div>}
        <Field label="Quantity (kg)">
          <input
            type="number"
            min="0"
            step="any"
            value={f.quantity_kg}
            onChange={set("quantity_kg")}
            autoFocus
          />
        </Field>
        <Field label="Rate (₹/kg)">
          <input
            type="number"
            min="0"
            step="any"
            value={f.unit_cost}
            onChange={set("unit_cost")}
          />
        </Field>
        <Field label="Linked order" hint="(optional)">
          <select value={f.order_id} onChange={set("order_id")}>
            <option value="">Not linked</option>
            {orders.map((o) => (
              <option key={o.id} value={o.id}>
                {o.order_no} — {o.fabric_type} ({o.colour})
              </option>
            ))}
          </select>
        </Field>
        <DialogActions
          saving={saving}
          onClose={onClose}
          isEdit
          saveLabel="Save correction"
        />
      </form>
    </Dialog>
  );
}

/* ---------- shared bits ---------- */
function Toolbar({ title, count, onAdd }) {
  return (
    <div className="toolbar">
      <h3>
        {title} <span className="muted">({count})</span>
      </h3>
      <button className="btn btn-primary btn-sm" onClick={onAdd}>
        ＋ Add
      </button>
    </div>
  );
}

function Dialog({ title, onClose, children }) {
  return (
    <div className="owner-drawer-backdrop" onClick={onClose}>
      <div
        className="owner-dialog"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={title}
      >
        <h3>{title}</h3>
        {children}
      </div>
    </div>
  );
}

function DialogActions({ saving, onClose, isEdit, saveLabel }) {
  return (
    <div className="form-actions" style={{ gap: "0.5rem" }}>
      <button
        type="button"
        className="btn btn-ghost btn-sm"
        onClick={onClose}
        disabled={saving}
      >
        Cancel
      </button>
      <button className="btn btn-primary btn-sm" disabled={saving}>
        {saving ? "Saving…" : saveLabel || (isEdit ? "Save changes" : "Add")}
      </button>
    </div>
  );
}
