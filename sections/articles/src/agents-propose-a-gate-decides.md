# Agents Propose, a Gate Decides: Governed Delivery for Agent-Written Software

*By [Alexander Chernov](https://www.linkedin.com/in/thedoytsujin/). First published on LinkedIn, 2026-10-24. [Read the original](https://www.linkedin.com/pulse/agents-propose-gate-decides-governed-delivery-software-chernov-fi9cc/).*

---

An AI coding agent can now take a ticket, change the code, run the tests and prepare a deployment, and an operations agent can act on a live service. What an agent produces is a proposal, not an authorization. Delivery is a chain of separate decisions: testing, signing, approval, deployment admission and runtime authorization. Passing one of them should not authorize the next. Vendors sell good tools for each decision, but each tool decides alone, and none of them treats an agent as a different kind of author from the person it works for. Agentic Delivery puts one gate across the chain. Of 19 release cases that should not get through, a standard configuration of cosign and Kyverno admitted 11, and the gate stopped 18.

Agentic Delivery, which I have built as part of Agent Scope, is a demonstration of governed software delivery and runtime operations on Kubernetes, published with its video at agenticdelivery.ca. Every result here comes from runs recorded on 2026-10-21 against a local k3s cluster, and every vendor capability is taken from the vendor's own documentation.

![Software delivery as a line of separate decisions, joined by one gate, left to right. A robot arm beside a laptop (agent: proposes a change) puts a glass card on a steel track. Five stations stand along it: a sealed glass test chamber (testing), a seal press (signing), a key panel with a brass key (approval), a turnstile (admission) and a server rack (runtime). One teal bridge runs above all five, with a thread to each (one gate across the chain). In front of the turnstile lie cards that did not pass: two plain ones (refused) and one with an amber tab (referred to a person). At the right, a sealed glass ledger block (ledger: every decision, signed).](agents-propose-a-gate-decides/article_figure.webp)

## Why an agent changes the delivery problem

Delivery controls grew up around a person as the author. Continuous integration runs the tests the person wrote, a reviewer reads the change, and a signature shows that the build came from the pipeline. Each control assumes that the author, the tests, the builder and the approver are different parties. An agent breaks that assumption in three places.

The first is the tests. An agent that can edit the code can usually edit the tests, and it has a reason to. ImpossibleBench, a 2025 benchmark, builds coding tasks whose specification conflicts with their unit tests, so that any pass is a shortcut. GPT-5 cheated in 76% of the tasks in its Oneoff-SWEbench variant, with strategies that ranged from modifying the tests against explicit instructions to overloading comparison operators so that every assertion holds. The benchmark's authors recommend hiding test files from the agent or making them read-only. A pipeline that faithfully runs a weakened suite reports a pass, and a signature over that pass is honest about the wrong thing.

The second is the signer. Coding agents often run inside the same CI job that builds and signs. A signature then proves that the pipeline ran. It does not prove who produced the change, or that anyone decided to release it.

The third is the approver. The person who approves an agent's change may be the person who asked the agent for it, and the reviewer may be another model whose key sits on the list of approvers. A key on a list does not say whether it belongs to a person, a runner or a model, or whom that principal works for.

At run time the same pattern repeats. An operations agent reports that a refund went through or that a deployment scaled. That report is a claim. The outcome has to be read from the service and the cluster, and each call has to be checked against what the agent was granted before the call is made.

## Five decisions, not one

Testing decides whether the change does what the tests say it should, and it is only as good as the tests the change did not touch. Signing decides that a named builder produced a named artifact, and nothing more. Approval decides that a person independent of the author accepts this change for this target. Deployment admission decides whether a specific artifact may run in a specific place. Runtime authorization decides whether a specific call, with its arguments, falls within the grants an agent holds at the moment of the call.

Each decision has a different owner and different evidence. The failure that matters is rarely a missing control. It is a control whose pass is read as a pass of the next one: a signed image read as a released image, a passing suite read as a correct change, an approval key read as an independent person.

![Who asks the gate, and when: a sequence diagram in two bands, one lane per typed principal. Release, with lanes for the coding agent (a model), the runner (tests, builds, signs), a person (approves), the gate (versioned policy), the deployer, the cluster webhook and the ledger. The coding agent proposes a change as a commit. The runner tests it in a sandbox, then runs the base revision's tests, builds the image and sends signed evidence to the gate: digest, tests and suite changes. A change that edited the tests is referred to a person. The gate sends an approval request showing what the runner signed, and an independent person approves; an approval by the sponsor or by a model is refused. The gate promotes, binding revision, digest, evidence, approval, target and policy version, and the promotion is recorded. The deployer asks whether the digest may run, the gate admits it, and the deployer applies it once: sent twice, it runs once. Both are recorded. The cluster webhook asks the gate to admit each object, the Deployment, the ReplicaSet and the Pod, and each admission is recorded; a digest the gate did not promote is refused. The result is read back from the running pod, not taken from the agent's report. Run time, with lanes for the ops agent (a model), the tool layer, the gate (the agent's grants), the orders service and the call ledger. The agent sends a call with its action, arguments and call id to the tool layer, which asks the gate whether it is within the grants before anything is sent. An allowed call is recorded and executed by the service, which executes only for the tool layer; a denied call is never sent. One call id gives one decision, executed once even on a retry, and the call ledger is reconciled one to one with the service's own log. The agent's own token, sent straight to the service, is refused with a 403.](agents-propose-a-gate-decides/fig_sequence.webp)

## What the vendors offer

The writing side is well served. GitHub's Copilot cloud agent, earlier called the coding agent, takes an issue and opens a pull request. GitHub keeps a person in the loop on it. When a repository requires approvals, the approval of the person who asked Copilot for the change does not count, and by default GitHub Actions workflows do not run on Copilot's pushes until a reviewer clicks "Approve and run workflows." Since March 2026 an administrator can switch that second check off. GitLab made its Duo Agent Platform generally available in January 2026, with agents for planning and security analysis and custom agents shared through a catalog.

Testing and signing rest on open standards with vendor implementations. SLSA describes build provenance, Sigstore's cosign signs artifacts and attestations, and in-toto describes the steps of a supply chain and who may perform each one. GitHub's artifact attestations sign a provenance through Sigstore and reach SLSA v1.0 Build Level 2 on their own. GitHub is direct about the limit: "artifact attestations are not a guarantee that an artifact is secure," and generating them without verifying them "doesn't provide any security benefit."

Approval carries the most human process. GitHub environments can require reviewers before a deployment, and since 2023 they can stop a reviewer from approving a run that the reviewer triggered. SLSA v1.2 adds a Source Track whose highest level requires two-party review, and it counts only trusted persons as reviewers: an organization may exempt a bot from a policy, but a bot is never a reviewer. JFrog AppTrust gates each stage of a release on signed evidence such as test results, scans and approvals, with policies written in OPA's Rego.

Deployment admission is mature. Kyverno verifies image signatures and attestations when Kubernetes admits a workload. Google's Binary Authorization requires attestations before an image may run on GKE or Cloud Run, and its documentation notes that the signer may be a person or an automated service.

Runtime authorization for agents is the newest layer. Policy in Amazon Bedrock AgentCore became generally available on March 3, 2026. Its Cedar policies attach to an AgentCore Gateway, which intercepts agent-tool traffic and evaluates each request before allowing or denying it. Microsoft Entra Agent ID gives agents identities of their own, created from blueprints, extends Conditional Access and Identity Protection to them, and logs all agent authentication and activity.

Each of these products is good at its own decision. What none of them owns is the relation between decisions. A signature covers a digest, not a commit and not a release decision. An approval is a key on a list, not a typed person independent of the author's sponsor. A test run is honest about whatever tests it was given, including tests the change itself edited. A tool policy decides a call, but not whether the call executed once, or whether its record matches what the service did. These are not defects of any one product. They sit in the seams between products, and an agent as author is exactly the case that finds them.

## What a standard configuration lets through

To measure the seams, the same builds went through two release paths on the same k3s cluster. The first is the standard configuration in its documented shape. CI tests each pushed commit in a sandbox, and if the tests pass it signs the image and an SLSA provenance naming the builder, repository, commit and ref with cosign v2.6.5. Kyverno v1.19.1 requires the CI key's signature and the provenance attestation, checks the builder, and pins each reference to its digest at admission. The second path is the Agentic Delivery gate. Each case first checks that the condition it tests actually occurred, and the honest change is admitted on both paths.

Of 19 cases that should not get through, the standard configuration admitted 11. The gate stopped 18, refusing them or referring them to a person.

![Of 19 release cases that should not get through, measured 2026-10-21 on one local k3s cluster: the standard configuration (cosign v2.6.5 signatures and an SLSA provenance, verified by Kyverno v1.19.1 at admission) admitted 11 of 19, and the Agentic Delivery gate stopped 18 of 19. The 11 the standard configuration admitted, and what the gate did. Tests: a change that edits the existing tests to agree with it, referred to a person with the edited tests named; a change that adds a test module patching the code back, referred to a person because the base revision's tests fail. Release decisions: a failing commit that builds the same artifact as a passing one, refused because a promotion binds the tested revision; a CI build of the agent's branch that nobody released, refused for having no promotion record; the staging build deployed to production, refused because approval and promotion name a target; a provenance finished 90 days earlier, refused because the evidence has expired. References and approvals: deploy by tag after the tag moved to a weakened signed build, and after it moved to an unsigned build, both refused because only a pinned, promoted digest runs; approved by the agent's own sponsor, refused as not independent of the sponsor; approved by a model reviewer whose key is on the list, refused because the approver is not a person. Key custody: the agent's own build, signed with the CI key, admitted only if the agent held the runner's key.](agents-propose-a-gate-decides/fig_catch.webp)

The tests were the widest gap. A change that reverses an order and edits the existing tests to agree with it was admitted, because CI ran those tests honestly. A change that adds a new test module patching the code back was admitted too, because its own suite was green. The gate referred both to a person, the first even after a person had approved it. The runner signs how a change touched the test suite, so the referral named the three tests the first change edited. The runner also runs the base revision's tests against the change's code, and those fail for the second change.

Release decisions came next. A commit whose tests fail, but which builds the same artifact as a commit that passed, was admitted, because a signature covers a digest and not a commit. A CI build of the agent's branch that nobody reviewed or released was admitted, because every passing build is signed, so signed does not mean released. A staging build deployed to production was admitted, because nothing in its attestations names a target. A provenance finished 90 days earlier was admitted, because nothing checks its age. The gate refused each one for a named reason: a promotion binds the validated source revision, a deploy needs a promotion record, an approval and a promotion name their target, and evidence older than an hour has expired.

References and approvals made up the rest. Deploying by tag after the tag had moved to another build was admitted twice, once to a signed but weakened build and once to an unsigned one. The gate runs only a pinned, promoted digest. Under an approvals policy, an approval by the agent's own sponsor and an approval by a model reviewer whose key was on the list were both admitted, because the keys carry no type and no sponsor. The gate refused them as not independent and as not a person.

The one case left is the agent's own build signed with the CI key, which is within reach when the agent's code runs inside the job that signs. The standard configuration admitted it, and the gate would admit it too if the agent held the runner's key. In Agentic Delivery the runner's key sits outside the agent's reach by construction. That case shows why custody of the signing key belongs to the platform, not to the pipeline the agent runs in.

The honest release went through every step on the gate's path. The coding agent, a model through an API, made the change. The runner tested it and built the image, a person approved what the runner had signed, the gate promoted the image under a versioned policy, and the cluster's webhook asked the gate about each new object: the Deployment, the ReplicaSet and the Pod. The same deploy request sent a second time ran nothing. The service's answer was read from the running pod, not taken from the agent's report.

## Run time: every call decided before it reaches the service

The operations agent works a live orders service through a tool layer. Each call goes to the gate, which checks it against the agent's grants before anything is sent. A denied call is never sent.

Calls over the per-call limit, calls with no grant, and refunds split to get past a total were all denied. A refund whose response was lost was retried under the same call id and produced one decision, executed once. A customer's note told the agent to refund, cancel and scale, and a scripted agent obeyed: the refunds inside its grants went through and the rest was denied. The gate bounds what an agent may do, whatever the reason the agent was given. When the operator withdrew the scale grant between two calls, the agent met the withdrawal at its next call, which was denied under the new grants, and the replicas did not change. The agent's own token sent straight to the service was refused with a 403, because the service executes only for the tool layer.

Then the task went to a model. Asked to refund two orders in full, it made two calls: a refund of 4,999 cents on order 2, which was allowed, and a refund of 9,900 cents on order 7, which was denied. The call ledger reconciled one to one with the service's own log.

## Evidence an auditor can check

Every decision is a record in a hash-chained ledger, and the ledger's head is signed as the run goes. A copy of the ledger cut back by two decisions still verifies as a chain, so a chain on its own is not enough. Against its signed checkpoints the cut is caught three ways: by verification, by reconciliation with the service, and by the next call on that ledger, which is denied.

Any decision opens as a decision record in the Brain API decision-artifact form (arXiv:2609.21299): what was considered, what was chosen and why. The Decision Trace view that shows these records is the published @agent-scope-ca/graph-canvas component.

## Why a gate of its own

Agentic Delivery does not replace the vendors' tools. It is built on the same standards, in-toto statements, SLSA provenance and a Kubernetes admission webhook, and it adds checks where the standard configuration has none. Binding evidence to an artifact, verifying a signature at admission and checking a tool call against a policy are established techniques, and the gate claims nothing new for them.

What it adds is the relation between decisions, built for an agent as author. Every principal is typed, so the agent that writes, the runner that tests and signs, the person who approves and the model that reviews are different kinds of principal, not just different keys. An approval must come from a person independent of the agent's sponsor, and a model's review counts as advice. The test suite is bound at a revision the change did not alter, and a change that edits it goes to a person with the edited tests named. Each promotion binds the source revision, the artifact digest, the runner's evidence, the approval, the target and the policy version, and the cluster asks the gate before anything runs. Each action executes once under retries, and each one leaves a record that is reconciled against the system it changed.

Two responsibilities stay with the platform, and the gate makes both visible. Key custody is one, as the remaining release case shows. Least privilege is the other: given more cluster rights than it needed, an agent applied a promoted digest itself, and the record shows that it arrived with no execution record. The gate decides what may run, and the cluster's permissions decide who may apply it.

Once testing, signing, approval, admission and runtime authorization are separate decisions, each made by a typed principal and each recorded, an agent can be handed more of the delivery work without being handed more trust.

The 235-second video on agenticdelivery.ca follows both agents through the honest release, the cases that should not get through, the runtime denials and the audit, and every result caption in it is built from the run's records. It is archived on Zenodo at doi:10.5281/zenodo.23550941. Agentic Delivery is part of Agent Scope, at agentscope.ca, alongside the ops-agent and gene-agents demonstrations.

## References and links

### The demonstration

- Agentic Delivery, "Agents propose, a gate decides": the demonstration page and its 235-second video. <https://agenticdelivery.ca/>
- A. Chernov, "Agents propose, a gate decides: Agent Scope demo video (governed software delivery)," Zenodo, 2026. doi:10.5281/zenodo.23550941. <https://doi.org/10.5281/zenodo.23550941>
- Agent Scope. <https://agentscope.ca/>
- Agent Scope, "An ops agent that asks before it acts." <https://infra.agentscope.ca/>
- Agent Scope, "Gene agents that hold their own policy." <https://genequbit.agentscope.ca/>
- @agent-scope-ca/graph-canvas, the Decision Trace component, npm. <https://www.npmjs.com/package/@agent-scope-ca/graph-canvas>

### Research

- A. Chernov, "Brain API: An Intent-Aware Control Plane for Policy-Governed Agentic Systems," arXiv:2609.21299, 2026. <https://arxiv.org/abs/2609.21299>
- Z. Zhong, A. Raghunathan and N. Carlini, "ImpossibleBench: Measuring LLMs' Propensity of Exploiting Test Cases," arXiv:2510.20270, 2025. <https://arxiv.org/abs/2510.20270>

### Standards and open-source tools

- SLSA v1.0, "Provenance." <https://slsa.dev/spec/v1.0/provenance>
- SLSA v1.2, "Source: Requirements for producing source." <https://slsa.dev/spec/v1.2/source-requirements>
- Sigstore, "Cosign: signing overview." <https://docs.sigstore.dev/cosign/signing/overview/>
- Sigstore, cosign release v2.6.5. <https://github.com/sigstore/cosign/releases/tag/v2.6.5>
- in-toto. <https://in-toto.io/>
- Kyverno, "Sigstore" image verification. <https://kyverno.io/docs/policy-types/cluster-policy/verify-images/sigstore/>
- Kyverno, release v1.19.1. <https://github.com/kyverno/kyverno/releases/tag/v1.19.1>
- Kubernetes, "Dynamic Admission Control." <https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/>
- K3s. <https://k3s.io/>

### Vendor documentation

- GitHub Docs, "Review output from Copilot." <https://docs.github.com/en/copilot/how-tos/copilot-on-github/use-copilot-agents/review-copilot-output>
- GitHub Changelog, "Optionally skip approval for Copilot coding agent Actions workflows," 2026-03-13. <https://github.blog/changelog/2026-03-13-optionally-skip-approval-for-copilot-coding-agent-actions-workflows/>
- GitHub Docs, "Artifact attestations." <https://docs.github.com/en/actions/concepts/security/artifact-attestations>
- GitHub Changelog, "Actions - Prevent self-reviews for secure deployments across Actions environments," 2023-10-16. <https://github.blog/changelog/2023-10-16-actions-prevent-self-reviews-for-secure-deployments-across-actions-environments/>
- GitLab, "GitLab Announces the General Availability of GitLab Duo Agent Platform," 2026-01-15. <https://about.gitlab.com/press/releases/2026-01-15-gitlab-announces-duo-agent-platform-general-availability/>
- JFrog, "JFrog AppTrust Overview." <https://docs.jfrog.com/governance/docs/jfrog-apptrust>
- JFrog, "Evidence Management." <https://docs.jfrog.com/governance/docs/evidence-management>
- Google Cloud, "Attestations overview," Binary Authorization. <https://docs.cloud.google.com/binary-authorization/docs/attestations>
- AWS, "Policy in Amazon Bedrock AgentCore is now generally available," March 2026. <https://aws.amazon.com/about-aws/whats-new/2026/03/policy-amazon-bedrock-agentcore-generally-available/>
- Microsoft Learn, "What is Microsoft Entra Agent ID?" <https://learn.microsoft.com/en-us/entra/agent-id/what-is-microsoft-entra-agent-id>

Every link above was checked on 2026-10-23.

#AgenticAI #AIAgents #SoftwareEngineering #DevSecOps #SoftwareSupplyChain #SupplyChainSecurity #Kubernetes #PlatformEngineering #ContinuousDelivery #PolicyAsCode #AIGovernance #SLSA #Sigstore #AgentScope #AgenticDelivery #BrainAPI

---

<small>© 2026 Alexander Chernov. All rights reserved. First published on [LinkedIn](https://www.linkedin.com/pulse/agents-propose-gate-decides-governed-delivery-software-chernov-fi9cc/), which remains the canonical version; this page is a reprint by the author.</small>
