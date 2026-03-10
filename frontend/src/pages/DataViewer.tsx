import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import type { VerticalCollectedData } from "../types";
import { getVerticalData } from "../api";
import ChannelSection from "../components/ChannelSection";
import DataCard from "../components/DataCard";

type Section = "channels" | "news" | "meta_ads" | "hashtags";

export default function DataViewer() {
  const { verticalId } = useParams<{ verticalId: string }>();
  const [data, setData] = useState<VerticalCollectedData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [section, setSection] = useState<Section>("channels");

  useEffect(() => {
    if (!verticalId) return;
    setLoading(true);
    getVerticalData(Number(verticalId))
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [verticalId]);

  if (loading) return <div className="page"><p>Loading...</p></div>;
  if (error) return <div className="page"><p className="error">{error}</p></div>;
  if (!data) return <div className="page"><p>No data</p></div>;

  const channelNames = Object.keys(data.channels);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Data Viewer &mdash; Vertical {data.vertical_id}</h1>
        <Link to="/" className="btn">Back to Verticals</Link>
      </div>

      {/* Section tabs */}
      <div className="tab-bar section-tabs">
        {(["channels", "news", "meta_ads", "hashtags"] as Section[]).map((s) => (
          <button
            key={s}
            className={`tab ${section === s ? "active" : ""}`}
            onClick={() => setSection(s)}
          >
            {s === "channels" && `Channels (${channelNames.length})`}
            {s === "news" && `News (${data.news.length})`}
            {s === "meta_ads" && `Meta Ads (${data.meta_ads.length})`}
            {s === "hashtags" && `Hashtags (${data.hashtags.length})`}
          </button>
        ))}
      </div>

      {/* Channels */}
      {section === "channels" && (
        <div>
          {channelNames.length === 0 ? (
            <p className="empty">No channel data collected yet.</p>
          ) : (
            channelNames.map((ch) => (
              <ChannelSection key={ch} name={ch} data={data.channels[ch]} />
            ))
          )}
        </div>
      )}

      {/* News */}
      {section === "news" && (
        <div className="card-grid">
          {data.news.length === 0 ? (
            <p className="empty">No news collected yet.</p>
          ) : (
            data.news.map((item) => <DataCard key={item.id} item={item} />)
          )}
        </div>
      )}

      {/* Meta Ads */}
      {section === "meta_ads" && (
        <div className="card-grid">
          {data.meta_ads.length === 0 ? (
            <p className="empty">No meta ads collected yet.</p>
          ) : (
            data.meta_ads.map((item) => <DataCard key={item.id} item={item} />)
          )}
        </div>
      )}

      {/* Hashtags */}
      {section === "hashtags" && (
        <div className="hashtag-list">
          {data.hashtags.length === 0 ? (
            <p className="empty">No hashtags collected yet.</p>
          ) : (
            data.hashtags.map((h) => (
              <span key={h.name} className="hashtag-chip">
                #{h.name}
                <small>{h.posts_count.toLocaleString()} posts</small>
              </span>
            ))
          )}
        </div>
      )}
    </div>
  );
}
