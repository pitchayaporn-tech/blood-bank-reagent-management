(function () {
  function initToasts() {
    document.querySelectorAll('[data-toast="true"]').forEach((el) => {
      const toast = bootstrap.Toast.getOrCreateInstance(el, { delay: 4500 });
      toast.show();
    });
  }

  function initDataTables() {
    if (!window.jQuery || !jQuery.fn || !jQuery.fn.DataTable) {
      return;
    }

    document.querySelectorAll('table[data-datatable="true"]').forEach((table) => {
      if (table.dataset.dtInitialized === "true") {
        return;
      }

      const bodyRows = table.tBodies && table.tBodies.length ? Array.from(table.tBodies[0].rows) : [];
      const onlyPlaceholderRows = bodyRows.length > 0 && bodyRows.every((row) => row.cells.length === 1 && row.cells[0].colSpan > 1);
      if (onlyPlaceholderRows) {
        table.tBodies[0].innerHTML = "";
      }

      const $table = jQuery(table);
      const hasActions = table.dataset.dtActions === "true";
      $table.DataTable({
        pageLength: 10,
        lengthMenu: [10, 25, 50, 100],
        order: [],
        autoWidth: false,
        dom: '<"d-flex flex-column flex-lg-row justify-content-between gap-2 align-items-lg-center mb-3"lfB>rt<"d-flex flex-column flex-lg-row justify-content-between align-items-lg-center gap-2 mt-3"ip>',
        buttons: [
          { extend: "copyHtml5", className: "btn btn-outline-primary btn-sm", text: '<i class="bi bi-copy me-1"></i>Copy' },
          { extend: "csvHtml5", className: "btn btn-outline-primary btn-sm", text: '<i class="bi bi-filetype-csv me-1"></i>CSV' },
          { extend: "excelHtml5", className: "btn btn-outline-primary btn-sm", text: '<i class="bi bi-file-earmark-excel me-1"></i>Excel' },
          { extend: "pdfHtml5", className: "btn btn-outline-primary btn-sm", text: '<i class="bi bi-filetype-pdf me-1"></i>PDF' },
          { extend: "print", className: "btn btn-outline-primary btn-sm", text: '<i class="bi bi-printer me-1"></i>Print' },
        ],
        columnDefs: hasActions ? [{ targets: -1, orderable: false, searchable: false }] : [],
      });

      table.dataset.dtInitialized = "true";
    });
  }

  function focusFirstInvalid() {
    const invalid = document.querySelector(".is-invalid");
    if (invalid) {
      invalid.focus({ preventScroll: false });
      invalid.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    initToasts();
    initDataTables();
    focusFirstInvalid();
  });
})();
