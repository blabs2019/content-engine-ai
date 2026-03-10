import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Vertical, VerticalCreate } from "../types";
import { getVerticals, createVertical, updateVertical, deleteVertical } from "../api";
import VerticalForm from "../components/VerticalForm";

export default function Verticals() {
  const [verticals, setVerticals] = useState<Vertical[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Vertical | null>(null);
  const navigate = useNavigate();

  const load = async () => {
    try {
      setLoading(true);
      setVerticals(await getVerticals());
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleSave = async (data: VerticalCreate) => {
    try {
      if (editing) {
        await updateVertical(editing.id, data);
      } else {
        await createVertical(data);
      }
      setShowForm(false);
      setEditing(null);
      load();
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this vertical?")) return;
    try {
      await deleteVertical(id);
      load();
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Verticals</h1>
        <button className="btn btn-primary" onClick={() => { setEditing(null); setShowForm(true); }}>
          + Add Vertical
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {loading ? (
        <p>Loading...</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Trigger</th>
              <th>Active</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {verticals.map((v) => (
              <tr key={v.id}>
                <td>{v.id}</td>
                <td>{v.name}</td>
                <td>{v.trigger_type}</td>
                <td>{v.is_active ? "Yes" : "No"}</td>
                <td>{new Date(v.created_at).toLocaleDateString()}</td>
                <td className="actions">
                  <button className="btn btn-sm" onClick={() => navigate(`/data/${v.id}`)}>
                    View Data
                  </button>
                  <button className="btn btn-sm" onClick={() => { setEditing(v); setShowForm(true); }}>
                    Edit
                  </button>
                  <button className="btn btn-sm btn-danger" onClick={() => handleDelete(v.id)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showForm && (
        <VerticalForm
          initial={editing}
          onSave={handleSave}
          onCancel={() => { setShowForm(false); setEditing(null); }}
        />
      )}
    </div>
  );
}
