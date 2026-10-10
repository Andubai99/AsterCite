import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { PROJECT_ROOT } from "../agent/assets.ts";
const value=JSON.parse(await readFile(join(PROJECT_ROOT,"demo/dialogue.json"),"utf8"));
console.log("AsterCite · 已保存的真实四轮对话回放（模型 API 调用 0）\n");
console.log("配置："+value.arm+"；对话："+value.dialogue_id+"。此命令展示已有记录，不生成新答案。\n");
for(const [index,t] of value.turns.entries()){
  console.log("轮次 "+(index+1)+"\n你："+t.question+"\nAgent："+t.answer);
  for(const s of t.sources)console.log("\n证据 "+s.paper_id+" / "+s.section+"\n["+s.chunk_id+"]\n"+s.text);
  console.log("\n");
}
