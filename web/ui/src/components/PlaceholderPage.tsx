/** 未实施页面的统一占位：标题 + 实施说明。 */
export function PlaceholderPage({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="page-view">
      <div className="view-head">
        <h2>{title}</h2>
      </div>
      <p className="placeholder-note">{desc}</p>
    </div>
  );
}
