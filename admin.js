async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", headers: { "Content-Type": "application/json" }, ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "请求失败");
  return data;
}
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const statusOptions = {
  reservations: ["待确认","已确认","测试中","已完成","已取消"],
  demands: ["待联系","方案沟通中","已报价","进行中","已完成","已关闭"],
  inquiries: ["未处理","跟进中","已回复","已关闭"]
};
function select(resource, item) {
  return `<select data-resource="${resource}" data-id="${item.id}">${statusOptions[resource].map((status) => `<option${status === item.status ? " selected" : ""}>${status}</option>`).join("")}</select>`;
}
function table(headers, rows) {
  if (!rows.length) return '<div class="empty">暂无记录</div>';
  return `<table><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table>`;
}
async function load() {
  try {
    const [summary, data] = await Promise.all([api("/api/admin/summary"), api("/api/admin/orders")]);
    const labels = { users:"用户", products:"项目", reservations:"预约", demands:"需求", inquiries:"咨询" };
    document.querySelector("#metrics").innerHTML = Object.entries(labels).map(([key,label]) => `<article class="metric"><b>${summary[key]}</b><span>${label}总数</span></article>`).join("");
    document.querySelector("#reservationTable").innerHTML = table(
      ["订单号","项目","用户","联系人","样品/要求","状态","时间"],
      data.reservations.map((item) => `<tr><td>${escapeHtml(item.order_no)}</td><td>${escapeHtml(item.product_title)}</td><td>${escapeHtml(item.user_email)}</td><td>${escapeHtml(item.contact_name)}<small>${escapeHtml(item.phone)}</small></td><td>${escapeHtml(item.sample_info)}<small>${escapeHtml(item.requirements)}</small></td><td>${select("reservations",item)}</td><td>${escapeHtml(item.created_at)}</td></tr>`)
    );
    document.querySelector("#demandTable").innerHTML = table(
      ["需求编号","标题","用户","类别/预算","详情","状态","时间"],
      data.demands.map((item) => `<tr><td>${escapeHtml(item.demand_no)}</td><td>${escapeHtml(item.title)}</td><td>${escapeHtml(item.user_email)}</td><td>${escapeHtml(item.category)}<small>${escapeHtml(item.budget)}</small></td><td>${escapeHtml(item.details)}</td><td>${select("demands",item)}</td><td>${escapeHtml(item.created_at)}</td></tr>`)
    );
    document.querySelector("#inquiryTable").innerHTML = table(
      ["姓名","电话","咨询内容","状态","时间"],
      data.inquiries.map((item) => `<tr><td>${escapeHtml(item.name)}</td><td>${escapeHtml(item.phone)}</td><td>${escapeHtml(item.message)}</td><td>${select("inquiries",item)}</td><td>${escapeHtml(item.created_at)}</td></tr>`)
    );
  } catch (error) {
    document.querySelector(".page").innerHTML = `<div class="error-box">${escapeHtml(error.message)}<br><a class="login-link" href="/">返回首页登录管理员账号</a></div>`;
  }
}
document.addEventListener("change", async (event) => {
  const control = event.target.closest("select[data-resource]");
  if (!control) return;
  control.disabled = true;
  try {
    await api(`/api/admin/${control.dataset.resource}/${control.dataset.id}`, { method:"PATCH", body:JSON.stringify({ status:control.value }) });
  } catch (error) {
    alert(error.message);
    await load();
  } finally {
    control.disabled = false;
  }
});
document.querySelector("#logoutButton").addEventListener("click", async () => {
  await api("/api/logout", { method:"POST", body:"{}" });
  location.href = "/";
});
load();
