import {datasets,jobs,sellouts} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {esc,fmt,notify,date} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';

export async function selloutPage(id){
 workspace.datasets=await datasets.list();
 workspace.sellouts = workspace.sellouts || {};
 const selectedId=Number(id)||workspace.selectedDataset||workspace.datasets[0]?.id;
 workspace.selectedDataset=selectedId;
 const list=selectedId?await sellouts.list(selectedId):[];
 workspace.sellouts[selectedId]=list;
 const writable=session.user.role!=='viewer';
 const dataset=workspace.datasets.find(d=>d.id===selectedId);
 const incomplete=list.filter(s=>!s.complete);
 const reportedTotal=list.reduce((sum,s)=>sum+(s.reported_supplement||0),0);
 const report=await latestReport(selectedId);
 const summary=report?.result?.basis;
 return heading('03 / SELLOUT LOG','售罄日登记与凭证补报','午餐卖光后，实领份数只是需求下限。登记售罄日并按凭证分批补报未领份数，报齐后才把「实领+未领」作为真实需求重算。')+
 '<div class="sellout-toolbar"><label>数据批次<select id="sellout-dataset" required>'+workspace.datasets.map(d=>'<option value="'+d.id+'" '+(d.id===selectedId?'selected':'')+'>'+esc(d.name)+' · '+d.rows+' 条</option>').join('')+'</select></label><div class="sellout-stats"><div><span>售罄日</span><strong>'+list.length+'</strong></div><div><span>未报齐</span><strong>'+(incomplete.length||0)+'</strong></div><div><span>已报未领合计</span><strong>'+fmt(reportedTotal)+'</strong></div></div></div>'+
 '<div class="two-columns sellout-columns"><section class="panel"><div class="section-title"><h2>登记售罄日</h2><span>实领自动取自批次</span></div><form id="sellout-form"><label>售罄日期<input type="date" name="date" required min="'+(dataset?.first_date||'')+'" max="'+(dataset?.last_date||'')+'"></label><div class="parameter-grid"><label>预计凭证份数<input type="number" name="expected_vouchers" min="1" max="50" value="1" required></label><label>实领份数（可选核对）<input type="number" step="any" name="served" placeholder="留空按批次取值"></label></div><label>备注<input name="note" placeholder="例如：周末团体餐售罄"></label><button type="submit" class="primary" '+(writable&&selectedId?'':'disabled')+'>登记售罄日</button><p class="hint">同一批次同一日期仅登记一次；实领份数只作为需求下限，不计入误差，直到凭证报齐。</p></form>'+
 '<div class="section-title"><h2>按凭证补报未领</h2></div><form id="supplement-form"><label>售罄日<select name="sellout_id" required>'+list.map(s=>'<option value="'+s.id+'">'+esc(s.date)+' · '+(s.complete?'已报齐':'待补 '+(s.expected_vouchers-s.voucher_count)+' 份凭证')+'</option>').join('')+(!list.length?'<option value="">请先登记售罄日</option>':'')+'</select></label><div class="parameter-grid"><label>凭证号<input name="voucher_no" required maxlength="80" placeholder="PC-20261103-A"></label><label>未领份数<input type="number" step="any" name="portions" min="0" required></label></div><label>备注<input name="note" placeholder="例如：候补登记"></label><button type="submit" class="primary" '+(writable&&list.length?'':'disabled')+'>补报此凭证</button><p class="hint">同一凭证号重试不会重复入账；份数不一致会拒绝并保留原记录。</p></form></section>'+
 '<section><div class="section-title"><h2>售罄日台账</h2><span>'+list.length+' 天 · 已报未领 '+fmt(reportedTotal)+' 份</span></div><div class="sellout-list">'+list.map(s=>selloutRow(s,writable)).join('')+(!list.length?'<div class="empty">尚无售罄日。午餐卖光当天先在此登记，再补报未领份数。</div>':'')+'</div>'+
 (summary?'<section class="panel"><div class="section-title"><h2>已冻结的分析依据</h2><span>最近任务 '+esc(report.name||'')+'</span></div><div class="basis-grid"><div><span>计入误差的日期</span><strong>'+(summary.error_dates?.length||0)+'</strong></div><div><span>保留位置但不计误差</span><strong>'+(summary.censored_dates?.length||0)+'</strong></div><div><span>售罄日已报齐</span><strong>'+(summary.complete_count||0)+'/'+(summary.sellout_count||0)+'</strong></div></div>'+(summary.censored_dates?.length?'<p class="hint">未报齐日期：'+summary.censored_dates.map(esc).join('、')+'。这些日期在回测中保留位置，但不把实领当真值。</p>':'<p class="hint">最近任务依据的售罄日已全部报齐，可按「实领+未领」重算。</p>')+(summary.error_dates?.length?'<p class="hint">计入误差的日期（'+summary.error_dates.length+' 天）：'+summary.error_dates.map(esc).join('、')+'</p>':'')+'</section>':'')+
 '</section></div>';
}

function selloutRow(s,writable){
 const pct=s.expected_vouchers?Math.min(100,Math.round(s.voucher_count/s.expected_vouchers*100)):0;
 return '<article class="sellout-card '+(s.complete?'complete':'open')+'"><div class="sellout-head"><div><strong>'+esc(s.date)+'</strong><span class="tag '+(s.complete?'ok':'pending')+'">'+(s.complete?'已报齐':'待补报')+'</span></div><small>'+esc(s.meal)+' · 登记 '+date(s.created_at)+'</small></div>'+
  '<div class="sellout-bars"><div><span>需求下限（实领）</span><b>'+fmt(s.demand_lower_bound)+'</b></div><div><span>已报未领</span><b>'+fmt(s.reported_supplement)+'</b></div><div><span>'+(s.complete?'重算需求':'报齐后需求')+'</span><b>'+(s.adjusted_demand!=null?fmt(s.adjusted_demand):'待报齐')+'</b></div></div>'+
  '<div class="voucher-progress"><span>凭证 '+s.voucher_count+'/'+s.expected_vouchers+'</span><i style="width:'+pct+'%"></i></div>'+
  (s.vouchers?.length?'<ul class="voucher-list">'+s.vouchers.map(v=>'<li><code>'+esc(v.voucher_no)+'</code><span>'+fmt(v.portions)+' 份</span>'+(v.note?'<small>'+esc(v.note)+'</small>':'')+'</li>').join('')+'</ul>':'')+
  (s.complete?'':'<p class="warning">尚未报齐：实领 '+fmt(s.demand_lower_bound)+' 份仅为需求下限，该日保留在序列中但不计误差。</p>')+
  '</article>';
}

async function latestReport(datasetId){
 if(!datasetId)return null;
 const all=await jobs.list();
 return all.filter(j=>j.dataset_id===datasetId&&j.status==='completed').sort((a,b)=>(b.finished_at||0)-(a.finished_at||0))[0]||null;
}

export function bindSellouts(refresh){
 document.querySelector('#sellout-dataset')?.addEventListener('change',e=>{workspace.selectedDataset=Number(e.target.value);location.hash='#/sellouts/'+e.target.value;});
 const registerForm=document.querySelector('#sellout-form');
 if(registerForm)submit(registerForm,async f=>{
   const data={date:f.get('date'),expected_vouchers:Number(f.get('expected_vouchers')),note:f.get('note')||''};
   const served=f.get('served');if(served!=='')data.served=Number(served);
   await sellouts.register(workspace.selectedDataset,data);notify('售罄日已登记，可继续按凭证补报');await refresh();
 });
 const supplementForm=document.querySelector('#supplement-form');
 if(supplementForm)submit(supplementForm,async f=>{
   const id=Number(f.get('sellout_id'));
   if(!id){notify('请先登记售罄日',true);return;}
   const r=await sellouts.supplement(id,{voucher_no:f.get('voucher_no'),portions:Number(f.get('portions')),note:f.get('note')||''});
   notify(r.duplicate?'该凭证已登记，未重复入账':'凭证已补报'+(r.complete?'，该售罄日已报齐':''));await refresh();
 });
}
