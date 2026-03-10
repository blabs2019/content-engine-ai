import { useState, useEffect } from "react";
import type { Vertical, VerticalCreate } from "../types";

interface Props {
  initial?: Vertical | null;
  onSave: (data: VerticalCreate) => void;
  onCancel: () => void;
}

export default function VerticalForm({ initial, onSave, onCancel }: Props) {
  const [name, setName] = useState("");
  const [triggerType, setTriggerType] = useState("manual");
  const [isActive, setIsActive] = useState(true);

  useEffect(() => {
    if (initial) {
      setName(initial.name);
      setTriggerType(initial.trigger_type);
      setIsActive(initial.is_active);
    }
  }, [initial]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave({ name, trigger_type: triggerType, is_active: isActive });
  };

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
        <h2>{initial ? "Edit Vertical" : "Add Vertical"}</h2>

        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>

        <label>
          Trigger Type
          <select value={triggerType} onChange={(e) => setTriggerType(e.target.value)}>
            <option value="manual">Manual</option>
            <option value="scheduled">Scheduled</option>
          </select>
        </label>

        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
          />
          Active
        </label>

        <div className="form-actions">
          <button type="submit" className="btn btn-primary">
            {initial ? "Update" : "Create"}
          </button>
          <button type="button" className="btn" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
