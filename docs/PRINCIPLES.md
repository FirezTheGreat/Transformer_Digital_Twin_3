# SKY HIGH — Track 2 Engineering Principles

> **PowerNext-AI Hackathon 2026 | CPRI | Digital Twin of a Distribution Transformer**

This document is the technical constitution of the project.

Every significant research, architecture, implementation, modelling, and engineering decision should be consistent with these principles. When a proposed approach conflicts with them, the conflict should be explicitly discussed before proceeding.

---

## 1. Engineering First, AI Second

We are building an **engineering system**, not an AI showcase.

Use ML/AI only when it provides a measurable advantage over a simpler engineering, statistical, or mathematical approach.

> Never add AI merely because the problem is labelled "AI."

---

## 2. Physics Before Prediction

Where transformer physics gives us a reliable relationship, prefer it over blindly learning the relationship from data.

Examples:

- Electrical relationships → physics
- I²R losses → physics
- Temperature rise → physical modelling
- Thermal behaviour → physics + data where appropriate
- Complex/unmodelled behaviour → ML where justified

ML should **complement physical understanding**, not replace it.

---

## 3. Every Output Must Have a Reason

Any important output should be explainable.

If the system says:

> Health Index = 63

we should be able to answer:

> **Why 63?**

If it says:

> Thermal anomaly detected

we should be able to answer:

> **What behaviour caused the anomaly?**

If it recommends maintenance:

> **Which observed conditions led to the recommendation?**

No black-box output should become an important engineering decision without an interpretable basis.

---

## 4. Never Manufacture Information

If the dataset doesn't contain a parameter, **do not silently invent it**.

We may:

- derive it from valid measurements,
- estimate it using a validated model,
- mark it unavailable,
- or degrade gracefully.

But we never pretend a measurement exists when it doesn't.

---

## 5. Dataset Independence

The development dataset is a **development vehicle, not the definition of the system**.

The CPRI dataset may have different column names, sampling rates, missing parameters, additional parameters, or different units.

Therefore:

```text
External Dataset
      ↓
Adapter / Canonicalization
      ↓
Core System
```

The core system must not depend tightly on the current dataset.

---

## 6. Graceful Degradation

Missing optional data must not crash the system.

If an analysis requires a parameter that isn't available:

- disable that analysis,
- use a justified alternative,
- reduce confidence,
- or clearly report that the analysis is unavailable.

**Never fabricate the missing input.**

---

## 7. Evidence > Assumptions

Separate:

- **Known:** directly supported by data/source
- **Derived:** mathematically calculated
- **Modelled:** estimated by a model
- **Assumed:** required engineering assumption
- **Hypothesized:** something we are investigating
- **Validated:** experimentally demonstrated

We should never present an assumption as an established fact.

---

## 8. Don't Overfit to the Dataset

A model that performs extremely well on our development dataset but fails when CPRI changes the schema or operating conditions is not a successful solution.

We optimize for:

> **Generalizable behaviour, not impressive development-set metrics.**

---

## 9. Don't Confuse Anomaly With Fault

An unusual observation is not automatically a transformer fault.

The system must distinguish, where possible:

```text
Normal variation
      vs
Operating-regime change
      vs
Sensor/data problem
      vs
Potential physical anomaly
```

A genuine change in operating conditions should not automatically trigger a fault alarm.

---

## 10. Prefer Simple Models That Can Be Defended

If a linear or physical model is sufficient, do not use a deep neural network merely because it sounds more sophisticated.

Model complexity must be justified by:

- performance,
- data characteristics,
- interpretability,
- or a real engineering requirement.

---

## 11. No Fake Precision

The system should not output precise failure dates or probabilities unless the available data and validation genuinely support that precision.

When uncertainty is high, communicate uncertainty.

A defensible:

> **Elevated thermal risk**

is better than an invented:

> **Failure probability = 87.34%**

---

## 12. Validation Is Part of the Feature

Every major analytical component needs a way to test whether it works.

For example:

**Digital Twin**

> Does predicted behaviour match observed behaviour?

**Anomaly detection**

> Does it detect injected/known abnormal behaviour without excessive false alarms?

**Health Index**

> Does it respond sensibly to worsening operating conditions?

**Maintenance**

> Does the recommendation logically follow from the detected condition?

No component is considered complete merely because it runs.

---

## 13. Modular by Design

Each major responsibility should have a clear boundary.

```text
Data Adapter
     ↓
Digital Twin
     ↓
Anomaly Engine
     ↓
Health Engine
     ↓
Prediction
     ↓
Maintenance Engine
     ↓
Presentation
```

One module should not contain the logic of five others.

This makes the system easier to test, replace, debug, and adapt to CPRI's dataset.

---

## 14. Deterministic Engineering, Probabilistic Intelligence

Where possible:

**Engineering decisions → deterministic and explainable**

**Predictions/estimations → probabilistic/data-driven**

For example:

```text
Physics → expected behaviour
ML → prediction/residual estimation
Rules → condition classification
GenAI → explanation
```

The LLM should not become the hidden decision-maker.

---

## 15. GenAI Is an Interface, Not the Source of Truth

Generative AI may explain structured system outputs, but the underlying engineering facts must come from our deterministic/data-driven engines.

```text
Sensors
 ↓
Analytics
 ↓
Structured facts
 ↓
GenAI
 ↓
Human-readable explanation
```

Never:

```text
Sensors → LLM → engineering truth
```

---

## 16. Build for the Hackathon Reality

The system must be **working before October 10**.

The hackathon dataset should require:

> adaptation, not reinvention.

Therefore we prioritize:

1. End-to-end functionality
2. Correctness
3. Robustness
4. Explainability
5. Demonstrability
6. Refinement

over unnecessary infrastructure.

---

## 17. No Premature Architecture Decisions

We don't choose models, databases, frameworks, algorithms, or services before understanding the requirement and data.

The order is:

```text
Problem
 ↓
Data
 ↓
Physical understanding
 ↓
Requirements
 ↓
Method
 ↓
Architecture
 ↓
Implementation
```

Not the other way around.

---

## 18. Research Before Reinventing

Before implementing an important methodology, check whether established approaches already exist.

Particularly for:

- Transformer Health Index
- Thermal modelling
- Transformer ageing
- Anomaly detection
- Predictive maintenance
- RUL estimation

We should build on established knowledge where appropriate rather than inventing arbitrary formulas.

---

## 19. Reproducibility

Someone else on the team should be able to:

```text
Clone
 ↓
Install
 ↓
Configure
 ↓
Run
 ↓
Reproduce
```

the same result.

Therefore:

- version dependencies,
- keep configuration explicit,
- document assumptions,
- keep preprocessing reproducible,
- avoid hidden manual steps.

---

## 20. Every Number Has a Provenance

For every important number, we should know where it came from.

Example:

```text
Health Index
    ↓
Components
    ↓
Inputs
    ↓
Raw measurements
```

If a threshold, weight, coefficient, or parameter comes from:

- literature → cite it
- CPRI → cite it
- physics → explain it
- our experiment → document how it was obtained
- assumption → explicitly label it

---

## 21. Separate Core Truth From Presentation

The dashboard should **visualize the system**, not define the system.

The backend/analytics engine should produce structured facts.

The frontend should present them.

We should never change an engineering calculation merely to make the dashboard look better.

---

## 22. Don't Optimize for Demo Theatre

A flashy feature that cannot survive questioning is worse than a simple feature that we can explain completely.

If the judges ask:

> "Why did your system produce this?"

we should be able to walk through the entire chain.

---

## 23. Fail Safely

When confidence is low:

> **Say so.**

When data is insufficient:

> **Say so.**

When a prediction cannot be justified:

> **Don't make it.**

A system that knows when it doesn't know is preferable to one that confidently produces unsupported conclusions.

---

## 24. Evidence Before Claims

We should distinguish between:

> "This model can theoretically do X."

and:

> "Our implementation demonstrated X on this dataset."

Only the second is an experimental result.

Never turn a theoretical capability into a claimed project result.

---

## 25. Keep the System Replaceable

Every major component should be replaceable without rewriting the entire system.

For example:

```text
Current anomaly model
        ↓
     [replace]
        ↓
New anomaly model
```

without changing data ingestion, Health Index, dashboard, or maintenance logic.

---

# Engineering & Code Quality

## 26. Minimal Code, Maximum Clarity

Do not add code unless it serves a clear requirement.

Prefer:

```text
simple + readable + sufficient
```

over:

```text
abstract + clever + unnecessarily extensible
```

Every class, interface, abstraction, dependency, and service should have a reason to exist.

> **Doing less is often better engineering.**

---

## 27. High-Quality Code Over High Quantity

Code should be:

- Readable
- Efficient
- Maintainable
- Testable
- Consistent
- Explicit where important

Avoid:

- Duplicate logic
- Unnecessary abstractions
- Giant functions
- Magic numbers
- Hidden side effects
- Premature optimization

Optimize where there is an actual bottleneck, not because optimization sounds good.

---

## 28. One Responsibility, Not One Class

We should maintain clear responsibilities, but **not create a class for every tiny operation**.

Good modularity means:

> **Logical separation of responsibilities, not maximum number of files/classes.**

---

## 29. Documentation Is Part of the Product

Documentation should explain:

- What the system does
- Why it does it
- How each module works
- Important assumptions
- Mathematical/physical reasoning
- Model choices
- Data transformations
- Configuration
- How to run it
- How to reproduce results
- Known limitations

Important engineering decisions should be documented **when they are made**, not reconstructed at the end.

---

## 30. IoT-Ready by Design

The system should remain compatible with the eventual real-world integration described by CPRI.

Our architecture should allow:

```text
CSV / Historical Dataset
          │
          ├──────→ Canonical Data Interface
          │
IoT / SCADA ┘
          ↓
     Core System
```

The current prototype does **not** need a full IoT infrastructure.

But the core system should not be tightly coupled to CSV files either.

---

## 31. Performance Is a Requirement

Efficiency matters at every layer:

- Avoid unnecessary data copies
- Avoid unnecessary database calls
- Avoid repeated calculations
- Process time-series data efficiently
- Keep model inference lightweight where possible
- Measure bottlenecks before optimizing

The system should be capable of handling substantially more data than our development sample without requiring a complete rewrite.

---

## 32. Consistency Over Convenience

Use consistent:

- Naming
- Units
- Data formats
- Error handling
- Logging
- API conventions
- Configuration
- Model interfaces

A new module should **fit the existing system**, rather than introducing its own conventions.

---

## 33. Build for Replacement, Not Dependency

No implementation detail should become unnecessarily entangled with the rest of the system.

We should be able to replace:

- Dataset
- ML model
- Anomaly detector
- Health Index methodology
- Database
- Frontend component

without rewriting unrelated parts.

---

## 34. Earn Complexity

Complexity must be justified.

Before adding something, ask:

> **What problem does this solve?**

Then:

> **Can we solve it more simply?**

Only introduce the more complex solution if the simpler one is demonstrably insufficient.

---

# Final Working Principle

> ## Build the simplest system that can make a technically defensible claim.

Not the most sophisticated system.

Not the most AI-heavy system.

Not the most impressive architecture diagram.

**The strongest claim we can actually prove.**

---

# Working Philosophy

Our default development loop is:

```text
Understand
    ↓
Research
    ↓
Model
    ↓
Implement
    ↓
Validate
    ↓
Document
    ↓
Review
```

And our core mindset is:

> **Physics before ML.**  
> **Evidence before assumptions.**  
> **Simplicity before complexity.**  
> **Quality before quantity.**  
> **Validation before claims.**  
> **Explainability before spectacle.**
