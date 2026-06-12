async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", headers: { "Content-Type": "application/json" }, ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "请求失败");
  return data;
}
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
function table(headers, rows) {
  if (!rows.length) return '<div class="empty">暂无记录</div>';
  return `<table><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table>`;
}
async function load() {
  try {
    const me = await api("/api/me");
    if (!me.user) throw new Error("请先登录");
    document.querySelector("#welcomeTitle").textContent = `${me.user.name}，您好`;
    const data = await api("/api/my/orders");
    document.querySelector("#reservationTable").innerHTML = table(
      ["订单号","项目","联系人","样品信息","状态","提交时间"],
      data.reservations.map((item) => `<tr><td>${escapeHtml(item.order_no)}</td><td>${escapeHtml(item.product_title)}</td><td>${escapeHtml(item.contact_name)}<small>${escapeHtml(item.phone)}</small></td><td>${escapeHtml(item.sample_info)}</td><td><span class="status-badge">${escapeHtml(item.status)}</span></td><td>${escapeHtml(item.created_at)}</td></tr>`)
    );
    document.querySelector("#demandTable").innerHTML = table(
      ["需求编号","标题","服务类型","预算","状态","提交时间"],
      data.demands.map((item) => `<tr><td>${escapeHtml(item.demand_no)}</td><td>${escapeHtml(item.title)}</td><td>${escapeHtml(item.category)}</td><td>${escapeHtml(item.budget || "待议")}</td><td><span class="status-badge">${escapeHtml(item.status)}</span></td><td>${escapeHtml(item.created_at)}</td></tr>`)
    );
  } catch (error) {
    document.querySelector(".page").innerHTML = `<div class="error-box">${escapeHtml(error.message)}<br><a class="login-link" href="/">返回首页登录</a></div>`;
  }
}
document.querySelector("#logoutButton").addEventListener("click", async () => {
  await api("/api/logout", { method: "POST", body: "{}" });
  location.href = "/";
});
load();
