/** Fresh explicit bounded benchmark. Loads question-only plans; Gold stays in the independent scorer. */
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { MainPaperHarness } from "../agent/session-main-v2.ts";
import { SessionBudget } from "../agent/budget.ts";
import { PROJECT_ROOT, loadAssets, createWorker, fileHash } from "../agent/assets.ts";
import { readConfig, createUserRuntime, containedPath, sha } from "../agent/config.ts";
import { RuntimeFailure, errorText, redactText } from "../agent/contracts.ts";
import { visibleTurn } from "../agent/cli.ts";
import type { ControlledSnapshot } from "../agent/main-controls.ts";
interface Row {arm:"A"|"C"|"C-no-reflect";role:"main"|"native_off"|"compression";item_id:string;case_id:string;session_key:string;turn_index:number;user_text:string;declared_scope:string[];before_turn?:string}
const flags=new Map<string,string>();let execute=false;
for(let i=2;i<process.argv.length;i++){const key=process.argv[i];if(key==="--execute"){execute=true;continue;}if(!["--arm","--role","--view","--limit","--run-id","--config"].includes(key)||!process.argv[i+1])throw new Error("Use --arm A|C|C-no-reflect --role main|native_off|compression --view all|intent|rewrite|boundary|e2e --limit N --run-id NAME [--execute] [--config PATH]");flags.set(key,process.argv[++i]);}
async function run(){
  const arm=flags.get("--arm")??"C-no-reflect",role=flags.get("--role")??"main",view=flags.get("--view")??"all";
  if(!["A","C","C-no-reflect"].includes(arm)||!["main","native_off","compression"].includes(role)||!["all","intent","rewrite","boundary","e2e"].includes(view)||role!=="main"&&view!=="all")throw new RuntimeFailure("INVALID_PLAN","Unsupported arm/role/view");
  const plan=JSON.parse(await readFile(join(PROJECT_ROOT,"reproduce/agent295/run-plan.json"),"utf8")) as {turns:Row[]};
  const views=JSON.parse(await readFile(join(PROJECT_ROOT,"reproduce/agent295/views.json"),"utf8")) as Record<string,string[]>;
  const eligible=plan.turns.filter(r=>r.arm===arm && r.role===role && (view==="all" || views[view].includes(r.case_id)));
  const limit=flags.has("--limit")?Number(flags.get("--limit")):eligible.length;
  if(!Number.isInteger(limit)||limit<1||limit>eligible.length)throw new RuntimeFailure("INVALID_PLAN","Limit exceeds the selected fixed view");
  const selected=eligible.slice(0,limit);
  if(view!=="all" && selected.some(r=>r.turn_index>1))throw new RuntimeFailure("INVALID_PLAN","This view contains dialogue-dependent turns. Use --view all to retain real history; score the view separately.");
  const selectedIds=new Set(selected.map(r=>r.item_id));
  if(selected.some(r=>r.turn_index>1 && eligible.some(p=>p.session_key===r.session_key && p.turn_index<r.turn_index && !selectedIds.has(p.item_id))))
    throw new RuntimeFailure("INVALID_PLAN","Limit would omit prerequisite turns");
  const summary={mode:"fresh_benchmark",arm,role,view,planned_turns:selected.length,max_model_attempts:selected.length*12,server_weights_revision:"unknown",actual_billing:"unknown",will_execute:execute};
  console.log(JSON.stringify(summary,null,2));if(!execute)return;
  const id=flags.get("--run-id");
  if(!flags.has("--limit")||!id||!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/u.test(id))throw new RuntimeFailure("INVALID_PLAN","Execution requires an explicit --limit and new --run-id");
  const config=await readConfig(PROJECT_ROOT,flags.get("--config")??"configs/model.local.json"),key=process.env.PIPAPER_API_KEY??"";
  if(!key.trim())throw new RuntimeFailure("MISSING_KEY","Set PIPAPER_API_KEY in this terminal");
  const assets=await loadAssets(PROJECT_ROOT,config);
  if(assets.indexVersion!=="pipaper-full-index-v1-64b1aa77167d5715")throw new RuntimeFailure("INVALID_INDEX","Historical agent295 plans require the separate 3801-chunk index. See reproduce/README.md; original47 uses the old index.");
  const directory=await containedPath(PROJECT_ROOT,".local/benchmarks/"+id);await mkdir(join(PROJECT_ROOT,".local/benchmarks"),{recursive:true});await mkdir(directory);
  const binding=sha(JSON.stringify({summary,config,selected,assets:assets.implementationId,runner:await fileHash(join(PROJECT_ROOT,"reproduce/run_agent.ts"))}));
  await writeFile(join(directory,"freeze.json"),JSON.stringify({...summary,binding,config,turns:selected},null,2)+"\n",{flag:"wx"});
  const budget=await SessionBudget.open(directory,binding,selected.length);
  const sdk=await createUserRuntime(config.model,key),sessions=new Map<string,MainPaperHarness>(),failed=new Set<string>();
  let worker:Awaited<ReturnType<typeof createWorker>>|undefined,active="";
  const make=async(snapshot?:ControlledSnapshot)=>MainPaperHarness.create({cwd:PROJECT_ROOT,worker:worker!,knownPaperIds:new Set(assets.publicPapers.map(p=>p.paper_id)),modelRuntime:sdk.runtime,model:sdk.model,secrets:[key],thinkingLevel:config.model.thinking_level,
    questionPreparation:"light-v1",controls:{arm:arm==="A"?"A":"C",reflect:arm==="C",compaction:role==="native_off"?"off":"native",reliability:"candidate",implementation_id:binding},
    controlledSnapshot:snapshot,p2:{profile:arm==="A"?"A":"B",executionVersion:"full-v1",indexVersion:assets.indexVersion,evidenceIndex:assets.evidenceIndex,publicPapers:assets.publicPapers,
      commonPrompt:assets.commonPrompt,nlu:arm!=="A",reflect:arm==="C",structuredMemory:arm!=="A",answerContract:"full-v1-json",stageOutputLimits:{question_frame:config.model.max_output_tokens,evidence_check:config.model.max_output_tokens,generation:config.model.max_output_tokens}},
    requestTimeoutMs:config.session.request_timeout_ms,turnTimeoutMs:config.session.turn_timeout_ms,authorizeRequest:async q=>budget.admit(active,q.request_id)});
  try{
    // The entire finite selection is reserved before the first provider attempt.
    for(const row of selected)await budget.reserve(sha(row.item_id),row.user_text);
    await mkdir(join(directory,"turns"));await mkdir(join(directory,"checkpoints"));worker=await createWorker(assets,config);
    for(const [i,row] of selected.entries()){
      active=sha(row.item_id);
      let result:unknown;
      if(failed.has(row.session_key))result={status:"error",failure_code:"DEPENDENCY_FAILED",requests:[],final_answer:"Prior real turn failed; no ideal history substitution.",citation_validity:{cited_ids:[]},final_request_id:null};
      else{
        let h=sessions.get(row.session_key);
        if(!h){h=await make();sessions.set(row.session_key,h);}
        if(row.before_turn==="compact")h.requestCompaction();
        if(row.before_turn==="restore"){const snapshot=h.snapshot();h.dispose();h=await make(snapshot);sessions.set(row.session_key,h);}
        const raw=await h.runTurn(row.user_text,row.declared_scope,active);result=visibleTurn(raw);
        if(raw.status!=="completed")failed.add(row.session_key);
        await writeFile(join(directory,"checkpoints",active+".json"),redactText(JSON.stringify(h.snapshot())+"\n",[key]),{flag:"wx"});
      }
      const freshRow={...row,item_id:id+"/"+row.item_id};
      const bytes=redactText(JSON.stringify({row:freshRow,record:result,mode:"fresh_benchmark",review_status:"pending_semantic_review"})+"\n",[key]);
      await writeFile(join(directory,"turns",active+".json"),bytes,{flag:"wx"});await budget.finish(active,sha(bytes));
      console.log((i+1)+"/"+selected.length+" "+row.case_id+" "+(result as {status:string}).status);
    }
    await writeFile(join(directory,"completion.json"),JSON.stringify({status:"finished",...budget.summary(),semantic_review:"pending",actual_billing:"unknown"})+"\n",{flag:"wx"});
  }finally{for(const h of sessions.values())h.dispose();worker?.close();await budget.close();}
}
try{await run();}catch(e){console.error(errorText(e,[process.env.PIPAPER_API_KEY??""]));process.exitCode=1;}
