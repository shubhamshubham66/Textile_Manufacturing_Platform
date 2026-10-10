// Buyer: Browse Products, Product Specifications, and Place New Order.
import { useState } from "react";
import { apiFetch } from "../../../lib/api.js";
import {
  Badge,
  Dialog,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Notice,
  PageHead,
  go,
  useApi,
} from "../../../components/super/kit.jsx";
import "../../../owner.css";

const n = (v) => Number(v || 0).toLocaleString("en-IN");
const rupee = (v) =>
  `₹${Number(v || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

// --------------------------------------------------------------------------- //
// Browse Products.
// --------------------------------------------------------------------------- //
export function BuyerProducts() {
  const { data, error, loading, reload } = useApi("/api/buyer/products", []);
  const [order, setOrder] = useState(null);
  const [msg, setMsg] = useState("");
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead
        title="Browse products"
        sub="Fabrics the mill offers — specifications, price and minimum order quantity."
      />
      <Notice onClose={() => setMsg("")}>{msg}</Notice>
      {data.products.length === 0 ? (
        <Empty>No products are listed right now.</Empty>
      ) : (
        <div className="sm-cards">
          {data.products.map((p) => (
            <article key={p.id} className="sm-person">
              <header>
                <div>
                  <strong>{p.name}</strong>
                  <small className="muted">
                    {p.fabric_type} · {p.colour}
                  </small>
                </div>
                <Badge value="ok" label={rupee(p.price_per_meter) + "/m"} />
              </header>
              <dl className="sm-mini">
                {p.gsm && (
                  <div>
                    <dt>GSM</dt>
                    <dd>{p.gsm}</dd>
                  </div>
                )}
                {p.width_inch && (
                  <div>
                    <dt>Width</dt>
                    <dd>{p.width_inch}"</dd>
                  </div>
                )}
                {p.composition && (
                  <div>
                    <dt>Composition</dt>
                    <dd>{p.composition}</dd>
                  </div>
                )}
                <div>
                  <dt>Min order</dt>
                  <dd>{n(p.min_order_meters)} m</dd>
                </div>
                <div>
                  <dt>Lead time</dt>
                  <dd>{p.lead_time_days} days</dd>
                </div>
              </dl>
              {p.description && (
                <p className="muted sm-small">{p.description}</p>
              )}
              <div className="sm-row-end">
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => setOrder(p)}
                >
                  Order this
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      {order && (
        <OrderDialog
          product={order}
          onClose={() => setOrder(null)}
          onDone={(t) => {
            setOrder(null);
            setMsg(t);
          }}
        />
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Product Specifications (table view).
// --------------------------------------------------------------------------- //
export function BuyerSpecs() {
  const { data, error, loading, reload } = useApi("/api/buyer/products", []);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead
        title="Product specifications"
        sub="Full technical specs for every fabric."
      />
      {data.products.length === 0 ? (
        <Empty>No products listed.</Empty>
      ) : (
        <section className="panel">
          <div className="owner-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Colour</th>
                  <th className="num">GSM</th>
                  <th className="num">Width</th>
                  <th>Composition</th>
                  <th>Finish</th>
                  <th className="num">Price/m</th>
                  <th className="num">Min order</th>
                  <th className="num">Lead time</th>
                </tr>
              </thead>
              <tbody>
                {data.products.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <strong>{p.name}</strong>
                      <small className="sm-sub">{p.fabric_type}</small>
                    </td>
                    <td>{p.colour}</td>
                    <td className="num">{p.gsm || "—"}</td>
                    <td className="num">
                      {p.width_inch ? `${p.width_inch}"` : "—"}
                    </td>
                    <td>{p.composition || "—"}</td>
                    <td>{p.finish || "—"}</td>
                    <td className="num">{rupee(p.price_per_meter)}</td>
                    <td className="num">{n(p.min_order_meters)} m</td>
                    <td className="num">{p.lead_time_days} d</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Place New Order (pick a product, enter quantity + delivery).
// --------------------------------------------------------------------------- //
export function BuyerNewOrder() {
  const { data, error, loading, reload } = useApi("/api/buyer/products", []);
  const [order, setOrder] = useState(null);
  const [msg, setMsg] = useState("");
  const [custom, setCustom] = useState(false);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />;
  return (
    <div className="module sm-page">
      <PageHead
        title="Place a new order"
        sub="Pick a product (or request a custom fabric). Your order goes to the Supermanager for review and pricing."
      >
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => {
            setCustom(true);
            setOrder({});
          }}
        >
          Custom request
        </button>
      </PageHead>
      <Notice onClose={() => setMsg("")}>{msg}</Notice>
      <div className="sm-cards">
        {data.products.map((p) => (
          <article key={p.id} className="sm-person">
            <header>
              <div>
                <strong>{p.name}</strong>
                <small className="muted">
                  {p.fabric_type} · {p.colour}
                </small>
              </div>
              <Badge value="ok" label={rupee(p.price_per_meter) + "/m"} />
            </header>
            <p className="muted sm-small">
              Min {n(p.min_order_meters)} m · {p.lead_time_days} days lead time
            </p>
            <div className="sm-row-end">
              <button
                className="btn btn-primary btn-sm"
                onClick={() => {
                  setCustom(false);
                  setOrder(p);
                }}
              >
                Order
              </button>
            </div>
          </article>
        ))}
      </div>
      {order && (
        <OrderDialog
          product={custom ? null : order}
          onClose={() => setOrder(null)}
          onDone={(t) => {
            setOrder(null);
            setMsg(t + " — track it under My Orders.");
          }}
        />
      )}
    </div>
  );
}

// Shared order dialog, used by Browse Products and Place New Order.
function OrderDialog({ product, onClose, onDone }) {
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  const [fabric, setFabric] = useState(product?.fabric_type || "");
  const [colour, setColour] = useState(product?.colour || "");
  const [qty, setQty] = useState(
    product ? String(product.min_order_meters || "") : "",
  );
  const [deadline, setDeadline] = useState("");
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function go() {
    if (!fabric.trim() || !colour.trim())
      return setErr("Enter the fabric and colour.");
    if (!qty || Number(qty) <= 0)
      return setErr("Enter the quantity in metres.");
    if (
      product &&
      product.min_order_meters &&
      Number(qty) < product.min_order_meters
    )
      return setErr(
        `Minimum order for ${product.name} is ${n(product.min_order_meters)} m.`,
      );
    if (!deadline || deadline < tomorrow)
      return setErr("Choose a delivery date after today.");
    setBusy(true);
    setErr("");
    try {
      const r = await apiFetch("/api/buyer/orders", {
        method: "POST",
        body: {
          fabric_type: fabric.trim(),
          colour: colour.trim(),
          quantity_meters: Number(qty),
          deadline,
          note: note.trim() || null,
          product_id: product ? product.id : null,
        },
      });
      onDone(`${r.order_no} sent for review`);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      title={product ? `Order ${product.name}` : "Custom order request"}
      onClose={onClose}
    >
      {product && (
        <p className="muted sm-small">
          {rupee(product.price_per_meter)}/m · min {n(product.min_order_meters)}{" "}
          m · {product.lead_time_days} days lead time
        </p>
      )}
      <ErrorBox error={err} />
      <Field label="Fabric">
        <input
          value={fabric}
          onChange={(e) => setFabric(e.target.value)}
          disabled={!!product}
        />
      </Field>
      <Field label="Colour">
        <input
          value={colour}
          onChange={(e) => setColour(e.target.value)}
          disabled={!!product}
        />
      </Field>
      <Field label="Quantity (metres)">
        <input
          type="number"
          min="1"
          value={qty}
          onChange={(e) => setQty(e.target.value)}
          autoFocus
        />
      </Field>
      <Field label="Needed by">
        <input
          type="date"
          min={tomorrow}
          value={deadline}
          onChange={(e) => setDeadline(e.target.value)}
        />
      </Field>
      <Field label="Note for the mill (optional)" wide>
        <textarea
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="GSM, finish, packing…"
        />
      </Field>
      <div className="sm-row-end">
        <button className="btn btn-ghost btn-sm" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary btn-sm" onClick={go} disabled={busy}>
          {busy ? "Sending…" : "Send for review"}
        </button>
      </div>
    </Dialog>
  );
}
