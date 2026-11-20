/** @typedef {{id:number,name:string,source:string,rows:number,checksum:string,sellout_revision:number}} Dataset */
/** @typedef {{id:number,name:string,dataset_id:number,status:string,result:Object,approved:boolean,stale:boolean|null,basis:Object}} AnalysisJob */
/** @typedef {{id:number,name:string,job_id:number,destination:string,next_run:number,enabled:boolean}} ReportSchedule */
/** @typedef {{id:number,dataset_id:number,date:string,served:number,demand_lower_bound:number,reported_supplement:number,adjusted_demand:number|null,expected_vouchers:number,voucher_count:number,complete:boolean,vouchers:Array}} SelloutDay */
export {};
