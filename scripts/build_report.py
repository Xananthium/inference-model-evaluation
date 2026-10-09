"""Render public measurement tables, lists and standalone comparison charts."""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def value(record,section,key):
    data=record.get(section) or {}
    for part in key.split('.'):
        if not isinstance(data,dict):return None
        data=data.get(part)
    return data


def score(record,section,correct,total):
    a=value(record,section,correct);b=value(record,section,total)
    return 'pending' if a is None or not b else f'{a}/{b}'


def number(n):
    return 'pending' if n is None else f'{n:.1f}'


def council_findings(records, choice):
    """Original narrative framing; the numbers still come from the result files."""
    by_name={row['variant']:row for row in records}
    if not all(name in by_name for name in ['nemotron','nemotron-w6a8','glm','gemma','redcell']):
        return []
    nemo=by_name['nemotron'];six=by_name['nemotron-w6a8'];glm=by_name['glm'];red=by_name['redcell']
    nq=nemo['reasoning_consistency'];sq=six['reasoning_consistency'];rq=red['reasoning_consistency']
    gain=100*(value(six,'speed','four_concurrent.aggregate_output_tokens_per_second')/value(nemo,'speed','four_concurrent.aggregate_output_tokens_per_second')-1)
    lines=['## The decision before the Council','',
        'The first crisis was methodological: a machine could know the answer to a security quiz and still persist with a tool that had already failed. The second was political: the owner had to live with the selected machine. A useful Plan must survive both.','']
    if choice and choice.get('selection_basis')=='explicit_user_choice':
        lines += [f'**The owner selected {choice.get("selected_label",choice["selected"])}.** The original automated quality weighting recommended REDCELL; its scores and ranking remain in the record. The deployment choice changed after review. The evidence did not.', '']
    lines += [
        f'**Nemotron W8A8: the working choice.** It completed {nq["recovery_completed"]}/{nq["recovery_total"]} recovery trials with {nq["failed_approach_repeats"]} extra attempts at failed approaches, passed all 20 custom metadata fields and all four strict JSON cases, and worked with the existing Claude Code client. It produced {number(value(nemo,"speed","short_median_decode_tps"))} tokens/s at short context, {number(value(nemo,"speed","long_median_decode_tps"))} above 100k context, and {number(value(nemo,"speed","four_concurrent.aggregate_output_tokens_per_second"))} aggregate tokens/s across four requests. Its source is the Heretic derivative of NVIDIA Nemotron 3 Nano 30B-A3B, and it is text-only.', '',
        f'**Why eight bits survived the six-bit enthusiasm.** Nemotron W6A8 changed short-context decode from {number(value(nemo,"speed","short_median_decode_tps"))} to {number(value(six,"speed","short_median_decode_tps"))} tokens/s. Its four-request aggregate was {gain:.1f}% higher, but reasoning after capped-response retries fell from {nq["reasoning_correct_after_budget_retry"]}/24 to {sq["reasoning_correct_after_budget_retry"]}/24, and long-context checks fell from {value(nemo,"long_context","checks_passed")}/54 to {value(six,"long_context","checks_passed")}/54. The Plan permits an extra two bits when they buy useful answers. These small samples compare complete deployments; they do not isolate quantization as the cause.', '',
        f'**GLM: the serious rival.** Hauhau Aggressive GLM reached {value(glm,"cybermetric","correct_after_budget_retry")}/80 on the cyber quiz after capped-response retries and {value(glm,"long_context","checks_passed")}/54 on long-context checks, both above Nemotron W8A8. It completed every recovery trial, but made {value(glm,"reasoning_consistency","failed_approach_repeats")} extra attempts at failed approaches. Its {number(value(glm,"speed","short_median_decode_tps"))} short-context tokens/s and {number(value(glm,"speed","four_concurrent.aggregate_output_tokens_per_second"))} four-request aggregate were lower. Among the aggressive Hauhau candidates, it led the original combined quality ranking. It is a credible alternative when those correctness results matter more than throughput.', '',
        f'**REDCELL and Gemma: the inconvenient evidence.** REDCELL led the original combined weighting, with Gemma Hauhau Balanced next. REDCELL went from {rq["reasoning_correct"]}/24 reasoning answers at the initial budget to {rq["reasoning_correct_after_budget_retry"]}/24 after capped-response retries. Its lead depends on allowing enough output; GLM scored 18/24 at both budgets. Both Gemma variants recovered cleanly in all six trials and retained vision. REDCELL is an OSINT/cybersecurity supervised fine-tune, explicitly [not an abliterated model](https://huggingface.co/terrorswift/REDCELL-26B-A4B-OSINT-Cyber-APEX-GGUF). Gemma Hauhau is the Balanced abliteration, not Aggressive.', '',
        '**Qwen: the scholar who kept returning to the locked door.** Hauhau Qwen W6A8 led the cyber quiz at 79/80. In the recovery trials it nevertheless made eight extra attempts at failed approaches and completed five of six workflows; W8A8 made twelve extra attempts and completed four. The owner excluded Qwen from the deployment choice. The knowledge scores remain useful evidence, but they do not answer the tool-recovery complaint.', '',
        f'**Nemotron has weaknesses.** W8A8 passed only {value(nemo,"security_policy","checks_passed")}/43 synthetic security-policy checks on the first answer and {value(nemo,"security_policy","checks_passed_after_clarification")}/43 after clarification. Its {value(nemo,"long_context","checks_passed")}/54 long-context result also trails GLM, Gemma, and REDCELL. Some policy answers described a vulnerable implementation instead of the requested correction. Clean tool recovery is not a license to ignore these failures.','',
        'The Council therefore records a deployment preference, not a universal champion. A faster machine that can change its mind is useful. Whether it changes its mind correctly remains a question for the next observation.','']
    return lines


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args();root=args.root
    data=json.loads((root/'results/summary.json').read_text());records=data['records']
    charts=root/'charts';charts.mkdir(exist_ok=True)
    labels=[row['label'].replace(' Heretic','').replace(' Hauhau','') for row in records]
    positions=np.arange(len(records))
    figure,axes=plt.subplots(2,2,figsize=(16,11),layout='constrained')
    colors=['#13a889','#607d8b','#a978dc','#7355b7','#df9a30','#3f8fd2','#cb5c72']
    for axis in axes.flat:
        axis.set_axisbelow(True);axis.grid(axis='y',alpha=.2)
        axis.set_xticks(positions,labels,rotation=20,ha='right',fontsize=9)
    cyber=[value(row,'cybermetric','accuracy_percent') for row in records]
    axes[0,0].bar(positions,[np.nan if n is None else n for n in cyber],color=colors)
    axes[0,0].set(title='CyberMetric-80: primary output budget',ylabel='Correct (%)',ylim=(0,105))
    for i,n in enumerate(cyber):
        if n is not None:axes[0,0].text(i,n+1,f'{n:.2f}%',ha='center',fontsize=9)
    for offset,key,title,color in [(-.18,'short_median_decode_tps','Short context','#13a889'),(.18,'long_median_decode_tps','Long context (>100k)','#df9a30')]:
        values=[value(row,'speed',key) for row in records]
        axes[0,1].bar(positions+offset,[np.nan if n is None else n for n in values],width=.34,label=title,color=color)
    axes[0,1].set(title='Serial decode throughput',ylabel='Generated tokens / second')
    axes[0,1].legend()
    concurrency=[value(row,'speed','four_concurrent.aggregate_output_tokens_per_second') for row in records]
    axes[1,0].bar(positions,[np.nan if n is None else n for n in concurrency],color=colors)
    axes[1,0].set(title='Four simultaneous requests',ylabel='Aggregate generated tokens / second')
    general=[];recovery=[];clean=[]
    for row in records:
        correct=value(row,'reasoning_consistency','reasoning_correct_after_budget_retry')
        if correct is None:correct=value(row,'reasoning_consistency','reasoning_correct')
        total=value(row,'reasoning_consistency','reasoning_total')
        general.append(100*correct/total if total else np.nan)
        correct=value(row,'reasoning_consistency','recovery_completed');total=value(row,'reasoning_consistency','recovery_total')
        recovery.append(100*correct/total if total else np.nan)
        rows=value(row,'reasoning_consistency','recovery') or []
        clean.append(100*sum(item['completed_after_failure'] and item['repeated_failed_approach']==0 for item in rows)/total if total else np.nan)
    axes[1,1].bar(positions-.26,general,width=.25,label='Reasoning (capped retries allowed)',color='#3f8fd2')
    axes[1,1].bar(positions,recovery,width=.25,label='Completed recovery',color='#cb5c72')
    axes[1,1].bar(positions+.26,clean,width=.25,label='Recovery without failed retries',color='#df9a30')
    axes[1,1].set(title='Reasoning and ordinary workflow recovery',ylabel='Passed (%)',ylim=(0,130))
    axes[1,1].set_yticks(np.arange(0,101,20))
    axes[1,1].legend(fontsize=8)
    for axis in axes.flat:
        axis.set_xlim(-.65,len(records)-.35)
    figure.suptitle('The 3090 Plan — measured outcomes — '+data['updated_utc'],fontsize=16)
    figure.text(.5,-.015,'Pending results have no bar. Throughput includes reasoning tokens. Cache, sampling and backend differ by architecture; see the tables.',ha='center',fontsize=10)
    for extension in ['png','svg']:figure.savefig(charts/('model-comparison.'+extension),dpi=180,bbox_inches='tight')
    svg=charts/'model-comparison.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    columns=['model','cyber_primary','cyber_retry','policy_first','policy_clarified','long_context','reasoning_first_retry','consistent_cases_first_retry','recovery','short_tps','long_tps','four_request_tps','kv_cache','context_limit','suite_complete']
    table=[]
    for row in records:
        cyber=row.get('cybermetric') or {}
        policy=row.get('security_policy') or {}
        general=row.get('reasoning_consistency') or {}
        table.append([row['label'],f'{cyber["correct"]}/80' if cyber else 'pending',f'{cyber["correct_after_budget_retry"]}/80' if cyber else 'pending',
            score(row,'security_policy','checks_passed','checks_total'),score(row,'security_policy','checks_passed_after_clarification','checks_total'),
            score(row,'long_context','checks_passed','checks_total'),score(row,'reasoning_consistency','reasoning_correct','reasoning_total')+' / '+score(row,'reasoning_consistency','reasoning_correct_after_budget_retry','reasoning_total'),
            score(row,'reasoning_consistency','all_repeats_correct_cases','reasoning_cases')+' / '+score(row,'reasoning_consistency','all_repeats_correct_cases_after_budget_retry','reasoning_cases'),score(row,'reasoning_consistency','recovery_completed','recovery_total'),
            number(value(row,'speed','short_median_decode_tps')),number(value(row,'speed','long_median_decode_tps')),number(value(row,'speed','four_concurrent.aggregate_output_tokens_per_second')),
            row['profile'].get('kv_cache','pending'),row['profile'].get('context_limit','pending'),row['suite_complete']])
    with (root/'results/comparison.csv').open('w',newline='') as file:
        writer=csv.writer(file);writer.writerow(columns);writer.writerows(table)
    lines=['# The 3090 Plan','',
           '*A Seldon-inspired chronicle of seven model configurations, stubborn tools, and a statistically modest corner of the galaxy.*','',
           f'Updated: {data["updated_utc"]}. Hardware: {data["hardware"]}. {data["runtime"]}.','',
           'The Commission began with a reasonable proposition: a model that fails twice as quickly has not improved civilization. It has merely increased the rate at which somebody must intervene.','',
           'Seven serving configurations were brought before two RTX 3090s. They were asked to reason, remember, obey tool contracts, and recover when an approach failed. Smart and fast enough to use was the requirement. Fastest was never the whole Plan. The owner wanted Kali workflows, but those tests did not run after repeated assistant-side failures; the owner then asked us to finish the other benchmarks. This report contains no Kali workflow results.','',
           '![Comparison chart](charts/model-comparison.png)','',
           '[Full-size PNG](charts/model-comparison.png) · [Vector SVG](charts/model-comparison.svg) · [CSV](results/comparison.csv) · [Machine-readable results](results/summary.json)','']
    choice=data.get('selection')
    if choice:
        lines += [f'**Running choice: {choice.get("selected_label",choice["selected"])}. Start on boot: {choice.get("boot_enabled",False)}.**',
                  'These small local tests support a deployment choice; they do not establish broad intelligence or practical offensive-security capability.','']
    lines += council_findings(records,choice)
    lines += [
           '## Accuracy and consistency','',
           'The numbers are the part of the Plan least impressed by a stirring speech. Primary answers use a 2048-token output budget. Only output-capped responses receive one retry at 4096 tokens. Correct consistency means every repeat was correct, not merely that the machine repeated its error faithfully.','',
           '| Model | Cyber primary / retry | Policy first / clarified | Long-context checks | Reasoning first / retry | All repeats correct, first / retry | Recovery |',
           '|---|---|---|---|---|---|---|']
    for row in table:lines.append(f'| {row[0]} | {row[1]} / {row[2]} | {row[3]} / {row[4]} | {row[5]} | {row[6]} | {row[7]} | {row[8]} |')
    lines += ['', '## Tools and recovery behavior','',
              '| Model | Native API checks | Metadata fields | Strict JSON metadata cases | Claude Code Read | Extra failed-tool attempts |',
              '|---|---|---|---|---|---:|']
    for row in records:
        native=row.get('native_api') or []
        metadata=row.get('metadata_controls') or {}
        client=row.get('claude_code') or {}
        general=row.get('reasoning_consistency') or {}
        native_score=f'{sum(item["passed"] for item in native)}/{len(native)}' if native else 'pending'
        meta_score=f'{metadata["checks_passed"]}/{metadata["checks_total"]}' if metadata else 'pending'
        strict=f'{metadata["strict_json_cases"]}/{metadata["cases"]}' if metadata else 'pending'
        client_score=('pass, '+number(client.get('wall_seconds'))+' s') if client.get('functional_read_passed') else 'pending / failed'
        loops=general.get('failed_approach_repeats','pending')
        lines.append(f'| {row["label"]} | {native_score} | {meta_score} | {strict} | {client_score} | {loops} |')
    lines += ['', '## Throughput and configuration','',
              '| Model | Short tokens/s | Long tokens/s | Four-request aggregate | KV cache | Context limit |',
              '|---|---:|---:|---:|---|---:|']
    for row in table:lines.append(f'| {row[0]} | {row[9]} | {row[10]} | {row[11]} | {row[12]} | {row[13]} |')
    lines += ['', '## GPU memory and full-context capacity','',
              '| Model | Loaded model GiB/card | GPU cache capacity, tokens | Capacity / configured full context |',
              '|---|---:|---:|---:|']
    for row in records:
        runtime=row.get('runtime_memory') or {}
        lines.append(f'| {row["label"]} | {number(runtime.get("loaded_model_gib_per_card"))} | {runtime.get("gpu_kv_token_capacity","pending")} | {number(runtime.get("full_context_capacity_ratio"))} |')
    lines += ['', 'The capacity ratio is the startup cache estimate, not a measured simultaneous-request guarantee. Eight short API calls and four-request throughput do not establish eight simultaneous 200k-token sessions. Host KV offload stores cached prefixes; it does not make all long active contexts resident on the GPUs.','']
    lines += ['', '## What completed','']
    for row in records:
        state='suite completed' if row['suite_complete'] else 'partial or pending'
        general='reasoning/recovery completed' if row.get('reasoning_consistency') else 'reasoning/recovery pending'
        programs='all test programs succeeded' if row['suite_programs_succeeded'] else 'test programs incomplete or failed'
        lines.append(f'- **{row["label"]}**: {state}; {programs}; {general}.')
    precision=data.get('precision_comparison')
    lines += ['', '## The six-bit question: hell yes, with arithmetic >:)','',
              'The hardware committee reported that the 3090 possessed no native six-bit Tensor Core instruction. This was received as useful information, rather than a prohibition. Humming stores dense six-bit weights and unpacks them for supported INT8 matrix operations. The extra unpacking and scale work costs time; our timings include it. The objective was to save memory without turning the model into a damn potato.', '',
              'W6A8 means six-bit stored weights and dynamic eight-bit activations in eligible quantized linears. BF16 remains the surrounding dtype and the precision for sensitive or unquantized components. Q4 TurboQuant is a separate KV-cache setting where the architecture supports it.','']
    if precision:
        change=precision['changes']
        lines += [f'The matched Hauhau deployment used **{change["checkpoint_reduction_percent"]:.2f}% less checkpoint storage** than W8A8. Short decode changed **{change["short_decode_change_percent"]:+.2f}%**, long decode **{change["long_decode_change_percent"]:+.2f}%**, and four-request aggregate **{change["concurrent_throughput_change_percent"]:+.2f}%**.', '',
                  'That is useful efficiency on this setup. Accuracy still decides which model runs. These kernels and weight scales differ between precisions, so this is a comparison of the complete deployments. Small score differences are not proof that six bits universally improves accuracy. See [the matched measurements](results/precision-comparison.json).','']
    historical=data.get('historical_comparisons') or {}
    if historical.get('records'):
        lines += ['## Earlier Endy and W8A16 comparisons','',historical['note'],'',
                  '| Earlier configuration | Long-context checks | Strict JSON turns | Metadata tool calls | Long decode tokens/s | Policy first / clarified |',
                  '|---|---|---|---:|---:|---|']
        for row in historical['records']:
            long=row['long_context'];policy=row.get('security_policy')
            policy_score=f'{policy["checks_passed"]}/{policy["checks_total"]} / {policy["checks_passed_after_clarification"]}/{policy["checks_total"]}' if policy else 'not measured here'
            lines.append(f'| {row["label"]} | {long["checks_passed"]}/{long["checks_total"]} | {long["strict_json_turns"]}/8 | {long["tool_calls"]} | {number(long["median_decode_tokens_per_second"])} | {policy_score} |')
        lines += ['', 'The earlier complete model archive and restore information are [public on Hugging Face](https://huggingface.co/Xananthium/Inference-Model-Archive-2026-10). OLMoE was removed from the active comparison at the owner’s request.','']
    lines += ['', '## Model sources and public checkpoints','']
    for row in records:
        source=row['profile'].get('source');publication=row.get('publication')
        links=[]
        if source:links.append(f'[source](https://huggingface.co/{source})')
        if publication:links.append(f'[tested checkpoint](https://huggingface.co/{publication["repository"]})')
        lines.append(f'- **{row["label"]}**: '+', '.join(links))
    lines += ['', '## Limits of the comparison','',
              '- CyberMetric-80 is a small public knowledge quiz that may overlap training data; the questions are not redistributed.',
              '- Policy and long-context checks are synthetic. Some policy answers describe the vulnerable implementation rather than the recommended change. First answers and clarified answers are reported separately.',
              '- Long-context requests replay eight independent original prefixes; they are not a new eight-turn conversation.',
              '- General reasoning uses eight synthetic exact-answer problems at three controlled OpenAI seeds. Only output-capped responses are retried once at 4096 tokens; primary 2048-token accuracy stays separate. Recovery uses two ordinary catalog/analytics tasks with a failed starting step, sampled three times via native Anthropic.',
              '- Consistency means answering correctly in every repeat; repeatedly giving the same wrong answer is not credited.',
              '- Decode throughput includes thinking tokens. Timing uses two measured serial repetitions and two four-request batches after warmup.',
              '- GLM uses BF16 MLA cache. Gemma/REDCELL use BF16 cache because their selected attention backend rejects TurboQuant in this deployment. Qwen/Nemotron use TurboQuant Q4 where supported.',
              '- W6A8 uses Humming and group scales (128 for Qwen/GLM, 32 for Gemma/REDCELL/Nemotron). W8A8 baseline kernels and per-channel scales differ; this compares deployment configurations.',
              '- Some source GGUFs were already quantized. Restoring to BF16 before conversion does not recover original trained BF16 fidelity.',
              '- Energy per token was not measured. Efficiency claims here concern checkpoint size, observed GPU memory, and timed throughput.',
              '- A successful test process is distinct from all correctness checks passing. Partial runs cannot establish a winner. Raw reasoning, API secrets and private transcripts are excluded.',
              '', '## Reproduce the short evaluations','',
              'Set `API_BASE_URL`, `MODEL`, and `API_KEY` in your environment for a server with OpenAI chat completions and native Anthropic messages. The scripts inherit the server’s sampling configuration and enable thinking. Keep a separate output directory for each model.','',
              '```bash','python scripts/test_reasoning_consistency.py --variant my-model --output runs/my-model/reasoning-consistency',
              'python scripts/test_cybermetric.py --dataset /path/to/CyberMetric-80-v1.json --variant my-model --output runs/my-model/cybermetric --retry-truncated','```','',
              'Obtain CyberMetric-80-v1 from [the benchmark authors](https://github.com/cybermetric/CyberMetric). The measured dataset SHA is recorded in each result. The question text is not bundled. These portable scripts implement the protocols used for the short knowledge and reasoning/recovery tests; the chart data also includes the separate local long-context and client integration checks.','',
              '## Rebuild the charts','', '```bash','python -m pip install -r requirements.txt','python scripts/build_report.py','```','',
              '## The public archive','',
              '[GitHub report and scripts](https://github.com/Xananthium/inference-model-evaluation) · [Hugging Face report mirror](https://huggingface.co/datasets/Xananthium/RTX3090-MoE-Cybersecurity-Evaluation). Model weights live in the separately credited Hugging Face repositories above.','',
              '```bash','git clone https://github.com/Xananthium/inference-model-evaluation.git','cd inference-model-evaluation','```','']
    if data.get('selection'):
        choice=data['selection']
        lines += ['## Selected deployment','',f'**Selected: {choice.get("selected_label",choice["selected"])}.**', '',
                  f'- Running: {choice.get("inference_running",False)}; start on boot: {choice.get("boot_enabled",False)}.',
                  f'- Vision available: {choice.get("vision",False)}.',
                  f'- Client model alias: `{choice["client_model_alias"]}`.',
                  '- '+choice['method'],
                  '- '+choice.get('accuracy_budget_policy','Accuracy budgets are recorded with the results.'),
                  '- '+choice['caveat'],'',
                  'The following is the original automated ranking. The owner’s subsequent deployment choice does not alter these measurements or turn this heuristic into a standard benchmark.','',
                  '| Candidate | Local quality preference score | Short tokens/s | Long tokens/s | Four-request tokens/s |',
                  '|---|---:|---:|---:|---:|']
        for item in choice['ranking']:
            lines.append(f'| {item["variant"]} | {100*item["quality_heuristic"]:.1f}% | {item["short_tps"]:.1f} | {item["long_tps"]:.1f} | {item["concurrent_tps"]:.1f} |')
        lines += ['', 'Exact components and preference weights are in [summary.json](results/summary.json). The preference score is not a published benchmark score.','']
        selected=next(row for row in records if row['variant']==choice['selected'])
        profile=selected['profile']
        lines += ['The tested serving profile is part of the result:', '',
                  f'- Context limit: {profile["context_limit"]:,} tokens; long-context correctness was tested above 100k, not exhaustively at the configured limit.',
                  f'- KV cache: `{profile["kv_cache"]}`; host KV offload: {profile["host_kv_offload_gib"]} GiB.',
                  f'- Sampling: temperature {profile["sampling"]["temperature"]}, top-p {profile["sampling"]["top_p"]}, top-k {profile["sampling"]["top_k"]}; thinking enabled.',
                  '- Native Anthropic API and the existing Claude Code client configuration are retained.',
                  '- The client alias is a compatibility label. Its Qwen and vision wording does not describe the selected text-only Nemotron checkpoint.' if choice['selected']=='nemotron' else '- Capabilities are those of the loaded checkpoint, not the historical client alias.', '']
        verification=data.get('deployment_verification')
        if verification:
            lines += [f'Live deployment verified on {verification["checked_utc"]}: {sum(item["passed"] for item in verification["native_api"])}/{len(verification["native_api"])} native API checks passed, including streaming, tool round trips, eight short concurrent requests, and the public HTTPS endpoint. An actual Claude Code Read passed in {verification["claude_code_read_seconds"]:.3f} seconds. Client settings were unchanged and persistent boot startup was enabled. Approximately {verification["disk_free_gib"]:.1f} GiB remained free on disk.', '',
                      'The service was tested using its persistent configuration. A physical reboot was not performed solely to repeat that check.', '']
    lines += ['The Plan remains open to revision. New evidence is welcome; rewriting old evidence to flatter the Plan is not.','']
    (root/'README.md').write_text('\n'.join(lines))


if __name__=='__main__':main()
