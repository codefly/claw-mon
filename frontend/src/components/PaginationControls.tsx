type PaginationControlsProps = {
  page: number;
  pageSize: number;
  totalItems: number;
  onPageChange: (nextPage: number) => void;
};

export function PaginationControls({
  page,
  pageSize,
  totalItems,
  onPageChange
}: PaginationControlsProps) {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const canGoPrev = page > 1;
  const canGoNext = page < totalPages;

  return (
    <div className="paginationWrap">
      <button type="button" className="ghostButton" disabled={!canGoPrev} onClick={() => onPageChange(page - 1)}>
        Prev
      </button>
      <span className="muted">
        Page {page} / {totalPages} ({totalItems} items)
      </span>
      <button type="button" className="ghostButton" disabled={!canGoNext} onClick={() => onPageChange(page + 1)}>
        Next
      </button>
    </div>
  );
}
