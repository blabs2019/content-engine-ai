import { useState } from "react";
import type { ChannelData } from "../types";
import DataCard from "./DataCard";

interface Props {
  name: string;
  data: ChannelData;
}

export default function ChannelSection({ name, data }: Props) {
  const [tab, setTab] = useState<"trending" | "all_time">("trending");

  const items = tab === "trending" ? data.trending : data.all_time_favourite;

  return (
    <div className="channel-section">
      <h3 className="channel-name">{name}</h3>

      <div className="tab-bar">
        <button
          className={`tab ${tab === "trending" ? "active" : ""}`}
          onClick={() => setTab("trending")}
        >
          Trending ({data.trending.length})
        </button>
        <button
          className={`tab ${tab === "all_time" ? "active" : ""}`}
          onClick={() => setTab("all_time")}
        >
          All-Time ({data.all_time_favourite.length})
        </button>
      </div>

      <div className="card-grid">
        {items.length === 0 ? (
          <p className="empty">No items</p>
        ) : (
          items.map((item) => <DataCard key={item.id} item={item} />)
        )}
      </div>
    </div>
  );
}
