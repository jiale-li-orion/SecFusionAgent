## Change

<!-- One behavior or capability per PR. State what changes for a reader of the repository. -->

## Owner and boundary

<!-- Which capability owns the behavior? Which packages/apps change together, and why can they not change independently? -->

## Verification

<!-- List the commands actually run and their observed result, not the commands you intend to run. -->

- [ ] `make lint`
- [ ] `make typecheck`
- [ ] `make test`

## Review baseline

| Question | Passing condition |
| --- | --- |
| Who owns the behavior? | One capability owner is identifiable |
| Is dependency direction stable? | Package graph is acyclic and consumers use public contracts |
| Where do external systems terminate? | Provider/source/storage details stay at adapter boundaries |
| How do failures propagate? | Error states, retries, timeouts, and termination are observable |
| How is correctness verified? | The relevant unit / integration / e2e / regression layer has coverage |

## Generated artifacts

<!-- If this change touches a generator, confirm the committed artifact was regenerated in the same change. -->
