    (function(){
      const tabButtons = document.querySelectorAll('.lib-tabs button');
      const searchInput = document.getElementById('lib-search');
      const docList = document.getElementById('doc-list');

      const SHEET_ID = '1khnOvG98gu_9QWfruG6O_yKrTjCYmkZTGqevNmseaPY';
      // Mỗi loại văn bản nằm ở 1 trang tính (gid) riêng trong cùng 1 Google Sheet — không dùng chung 1 trang.
      const CATEGORY_GIDS = {
        'QCVN': '0',
        'TCVN': '1324347140',
        'C07': '1044962646',
        'Luật': '404686746',
        'Nghị định': '2127739445',
        'Thông tư': '1815798512',
        'Khác': '1854171887',
      };
      const DRIVE_DOCS = [];
      const FALLBACK_DOCS = [
        { title:'QCVN 06 SỬA ĐỔI BỔ SUNG 10.2023.pdf', type:'QCVN', link:'https://drive.google.com/file/d/1JAFq7bL1wjhsCFFlsoi1ky8m5q9v5pav/view?usp=sharing' },
        { title:'QCVN 10-2025-BCA Trang bị phương tiện phòng cháy-Bố trí phương tiện chữa cháy-Trang bị và bố trí phương tiện cứu nạn, cứu hộ.pdf', type:'QCVN', link:'https://drive.google.com/file/d/1SoKGt8nlc7IRQq9-Dd4iGE7XTW-kf5te/view?usp=sharing' },
        { title:'QCVN 02-2020-BCA về trạm bơm nước chữa cháy.pdf', type:'QCVN', link:'https://drive.google.com/file/d/1vUeaqjAG4aQjoei-H-8UXPP1xdYMnz45/view?usp=sharing' },
        { title:'QCVN 10-2012-BCT về an toàn trạm cấp khí dầu mỏ hóa lỏng.pdf', type:'QCVN', link:'https://drive.google.com/file/d/1l2qVjCYwoN2q7jmPk6j382ufpnOEFFvN/view?usp=sharing' },
        { title:'QCVN 02-2020-BCT về an toàn bồn chứa khí dầu mỏ hóa lỏng.pdf', type:'QCVN', link:'https://drive.google.com/file/d/1DidyQR4cS9eeULmZrw50bEqoJVnfcTUW/view?usp=sharing' },
      ];

      const docStatus = document.getElementById('doc-status');

      function setStatus(message, isError = false) {
        docStatus.textContent = message;
        docStatus.classList.toggle('error', isError);
      }

      function splitCsvLine(line) {
        const result = [];
        let cur = '';
        let inQuotes = false;
        for (let i = 0; i < line.length; i += 1) {
          const ch = line[i];
          if (inQuotes) {
            if (ch === '"') {
              if (line[i + 1] === '"') {
                cur += '"';
                i += 1;
              } else {
                inQuotes = false;
              }
            } else {
              cur += ch;
            }
          } else if (ch === '"') {
            inQuotes = true;
          } else if (ch === ',') {
            result.push(cur);
            cur = '';
          } else {
            cur += ch;
          }
        }
        result.push(cur);
        return result;
      }

      function parseCSV(text) {
        const lines = text.split(/\r?\n/).filter(line => line.trim().length > 0);
        const header = splitCsvLine(lines[0]).map(h => h.trim());
        return lines.slice(1).map(line => {
          const values = splitCsvLine(line);
          const row = {};
          header.forEach((key, idx) => {
            row[key] = (values[idx] || '').trim();
          });
          return row;
        });
      }

      function normalizeLink(raw) {
        if (!raw) return '';
        const trimmed = raw.trim();
        if (trimmed.startsWith('http')) return trimmed;
        const idMatch = trimmed.match(/[A-Za-z0-9_-]{20,}/);
        if (idMatch) {
          return `https://drive.google.com/file/d/${idMatch[0]}/view?usp=sharing`;
        }
        return trimmed;
      }

      async function fetchCategoryDocs(type, gid) {
        const url = `https://docs.google.com/spreadsheets/d/${SHEET_ID}/export?format=csv&gid=${gid}`;
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`Không tải được trang "${type}": ${response.status}`);
        }
        const csvText = await response.text();
        return parseCSV(csvText)
          .filter(row => row['TÊN'] && row['ID'])
          .map(row => ({ title: row['TÊN'], type, link: normalizeLink(row['ID']) }));
      }

      async function loadDocs() {
        const entries = Object.entries(CATEGORY_GIDS);
        const results = await Promise.allSettled(entries.map(([type, gid]) => fetchCategoryDocs(type, gid)));

        const loaded = [];
        const failed = [];
        results.forEach((r, i) => {
          const [type] = entries[i];
          if (r.status === 'fulfilled') loaded.push(...r.value);
          else { failed.push(type); console.error(r.reason); }
        });

        if (loaded.length) {
          DRIVE_DOCS.splice(0, DRIVE_DOCS.length, ...loaded);
          setStatus(
            failed.length
              ? `Đã tải ${DRIVE_DOCS.length} tài liệu (riêng trang "${failed.join('", "')}" không tải được, thử lại sau).`
              : `Đã tải ${DRIVE_DOCS.length} tài liệu từ Google Sheet.`,
            failed.length > 0
          );
        } else {
          setStatus('Không tải được danh sách sheet. Sử dụng danh sách mặc định.', true);
          DRIVE_DOCS.splice(0, DRIVE_DOCS.length, ...FALLBACK_DOCS);
        }
        renderDocs('QCVN', searchInput.value);
      }

      function renderDocs(filterType, filterText){
        const q = (filterText||'').trim().toLowerCase();
        const items = DRIVE_DOCS.filter(d => {
          const matchesType = d.type === filterType;
          const matchesText = !q || d.title.toLowerCase().includes(q);
          return matchesType && matchesText;
        });

        if(!items.length){
          docList.innerHTML = '<div style="color:var(--ink-soft);padding:18px;border:1px solid rgba(46,58,78,.08);border-radius:18px;background:#fff">Không tìm thấy văn bản nào. Thử tìm kiếm khác hoặc chuyển tab.</div>';
          return;
        }

        docList.innerHTML = items.map(d => `
          <div class="doc-card" data-link="${d.link || ''}" data-title="${d.title.replace(/"/g,'&quot;')}">
            <div class="doc-card-left">
              <span class="doc-dot"></span>
              <div>
                <strong class="doc-card-title">${d.title}</strong>
                <div class="doc-card-sub">Chạm để mở tài liệu</div>
              </div>
            </div>
            <button class="btn-open" type="button">Mở file</button>
          </div>
        `).join('');

        docList.querySelectorAll('.btn-open').forEach(btn => {
          btn.addEventListener('click', () => {
            const card = btn.closest('.doc-card');
            const link = card.dataset.link;
            const title = card.dataset.title;
            const targetUrl = link || 'https://drive.google.com/drive/search?q=' + encodeURIComponent(title);
            window.open(targetUrl, '_blank');
          });
        });
      }

      function setActiveTab(button){
        tabButtons.forEach(b => b.classList.remove('active'));
        button.classList.add('active');
      }

      tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
          setActiveTab(btn);
          renderDocs(btn.dataset.q, searchInput.value);
        });
      });

      searchInput.addEventListener('input', () => {
        const active = document.querySelector('.lib-tabs button.active');
        renderDocs(active.dataset.q, searchInput.value);
      });

      loadDocs();
    })();
