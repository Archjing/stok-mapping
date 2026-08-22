/** 研究对照图页：iframe 嵌入后端原样生成的原站研究页（SVG 图 + 说明文字）。 */
export function ResearchComparisonPage({ slug, title }: { slug: string; title: string }) {
  return (
    <div className="page-view page-view-flush">
      <div className="view-head">
        <h2 className="view-title">{title}</h2>
      </div>
      <iframe
        title={title}
        src={`/api/research/comparison/${slug}/page`}
        style={{ width: '100%', height: 560, border: '1px solid var(--ui-hairline)', background: 'transparent' }}
      />
    </div>
  );
}
