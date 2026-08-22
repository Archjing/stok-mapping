/** A股影响因子全景图（marklogseq 静态导出，iframe 嵌入 /api/research/wiki 原样展示）。 */
export function WikiPage() {
  return (
    <div className="page-view page-view-flush">
      <iframe
        title="A股影响因子全景图"
        src="/api/research/wiki"
        style={{ width: '100%', height: 'calc(100vh - 120px)', border: 'none' }}
      />
    </div>
  );
}
