import type { CollectedDataItem } from "../types";

interface Props {
  item: CollectedDataItem;
}

function formatScore(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toFixed(0);
}

export default function DataCard({ item }: Props) {
  const meta = item.platform_metadata ?? {};

  return (
    <div className="data-card">
      <div className="data-card-header">
        <span className="badge">{item.content_type}</span>
        {item.reach_score > 0 && (
          <span className="reach-score" title="Reach score">
            {formatScore(item.reach_score)}
          </span>
        )}
      </div>

      <h4 className="data-card-title">
        {item.url ? (
          <a href={item.url} target="_blank" rel="noreferrer">
            {item.title.slice(0, 120)}
          </a>
        ) : (
          item.title.slice(0, 120)
        )}
      </h4>

      <div className="data-card-meta">
        {item.published_at && (
          <span>{new Date(item.published_at).toLocaleDateString()}</span>
        )}
        {(meta.likes as number) > 0 && <span>Likes: {formatScore(meta.likes as number)}</span>}
        {(meta.comments as number) > 0 && <span>Comments: {formatScore(meta.comments as number)}</span>}
        {(meta.views as number) > 0 && <span>Views: {formatScore(meta.views as number)}</span>}
      </div>

      {item.tags && item.tags.length > 0 && (
        <div className="data-card-tags">
          {item.tags.slice(0, 5).map((t) => (
            <span key={t} className="tag">
              #{t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
