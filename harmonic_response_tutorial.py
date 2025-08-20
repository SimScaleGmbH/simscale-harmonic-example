#!/usr/bin/env python3
"""SimScale Harmonic Response Analysis Example"""

import os
import time
import sys
from simscale_sdk import *
from simscale_sdk.models import *

api_key = os.getenv("SIMSCALE_API_KEY")
if not api_key:
    print("ERROR: Please set SIMSCALE_API_KEY environment variable")
    sys.exit(1)

# Initialize API client
config = Configuration()
config.api_key['X-API-KEY'] = api_key
api_client = ApiClient(config)

projects_api = ProjectsApi(api_client)
storage_api = StorageApi(api_client)
geometry_imports_api = GeometryImportsApi(api_client)
simulations_api = SimulationsApi(api_client)
mesh_operations_api = MeshOperationsApi(api_client)
simulation_runs_api = SimulationRunsApi(api_client)
geometries_api = GeometriesApi(api_client)

print("Creating project...")
project = projects_api.create_project(Project(
    name="Harmonic Response Example",
    description="Harmonic response analysis example",
    measurement_system="SI"
))
project_id = project.project_id

# Upload geometry
print("Uploading geometry...")
storage = storage_api.create_storage()
with open("./fixtures/bracket-1.step", "rb") as f:
    api_client.rest_client.PUT(
        url=storage.url,
        headers={"Content-Type": "application/octet-stream"},
        body=f.read()
    )

# Import geometry
geometry_import = geometry_imports_api.import_geometry(
    project_id,
    GeometryImportRequest(
        name="Bracket",
        location=GeometryImportRequestLocation(storage.storage_id),
        format="STEP",
        input_unit="m",
        options=GeometryImportRequestOptions(facet_split=False, sewing=False, improve=True)
    )
)

# Wait for import
print("Importing geometry...")
while geometry_import.status not in ("FINISHED", "FAILED"):
    time.sleep(5)
    geometry_import = geometry_imports_api.get_geometry_import(
        project_id, geometry_import.geometry_import_id
    )

geometry_id = geometry_import.geometry_id

# Get body name for material assignment
bodies = geometries_api.get_geometry_mappings(
    project_id, geometry_id, _class='region', limit=1
).embedded
body_name = bodies[0].name if bodies else "region1"

# Define simulation
print("Setting up simulation...")
simulation = simulations_api.create_simulation(
    project_id,
    SimulationSpec(
        name="Harmonic Response",
        geometry_id=geometry_id,
        model=HarmonicAnalysis(
            element_technology=SolidElementTechnology(
                element_technology3_d=ElementTechnology(
                    definition_method=AutomaticElementDefinitionMethod(type="AUTOMATIC")
                )
            ),
            global_physics=SolidGlobalPhysics(enable_global_damping=False),
            model=SolidModel(),
            materials=[
                SolidMaterial(
                    name="Steel",
                    material_behavior=LinearElasticMaterialBehavior(
                        type="LINEAR_ELASTIC",
                        directional_dependency=IsotropicDirectionalDependency(
                            type="ISOTROPIC",
                            youngs_modulus=DimensionalFunctionPressure(
                                value=ConstantFunction(type="CONSTANT", value=200e9),
                                unit="Pa"
                            ),
                            poissons_ratio=ConstantFunction(type="CONSTANT", value=0.3)
                        )
                    ),
                    density=DimensionalFunctionDensity(
                        value=ConstantFunction(type="CONSTANT", value=7850),
                        unit="kg/m³"
                    ),
                    topological_reference=TopologicalReference(entities=[body_name])
                )
            ],
            initial_conditions=SolidInitialConditions(),
            boundary_conditions=[
                FixedSupportBC(
                    type="FIXED_SUPPORT",
                    name="Fixed Support",
                    topological_reference=TopologicalReference(
                        entities=["B1_TE42", "B1_TE70", "B1_TE98", "B1_TE378"]
                    )
                ),
                ForceLoadBC(
                    type="FORCE_LOAD",
                    name="Force",
                    force=DimensionalVectorFunctionForce(
                        value=ComponentVectorFunction(
                            type="COMPONENT",
                            x=ConstantFunction(type="CONSTANT", value=0),
                            y=ConstantFunction(type="CONSTANT", value=0),
                            z=ConstantFunction(type="CONSTANT", value=-1000)
                        ),
                        unit="N"
                    ),
                    topological_reference=TopologicalReference(
                        entities=["B1_TE150", "B1_TE153"]
                    )
                )
            ],
            numerics=SolidNumerics(
                harmonic_solution_method="MODAL_BASED",
                modal_base=ModalSolver(
                    solver=MUMPSSolver(type="MUMPS"),
                    solver_model={},
                    calculate_frequency=CalculateFrequency(
                        prec_shift=0.05, max_iter_shift=3, threshold_frequency=0.01
                    ),
                    eigen_mode=EigenModeVerification(threshold=1e-06, precision_shift=0.05)
                ),
                harmonic_response=ModalSolver(solver=MUMPSSolver(type="MUMPS"))
            ),
            simulation_control=SolidSimulationControl(
                modal_base=ModalBaseControl(
                    eigenfrequency_scope=FirstMode(type="FIRSTMODE", number_of_modes=10)
                ),
                harmonic_response=HarmonicResponseControl(
                    excitation_frequencies=FrequencyList(
                        type="LIST_V20",
                        start_frequency=DimensionalFrequency(value=10, unit="Hz"),
                        end_frequency=DimensionalFrequency(value=1000, unit="Hz")
                    )
                ),
                processors=ComputingCore(num_of_processors=-1),
                max_run_time=DimensionalTime(value=18000.0, unit="s")
            ),
            result_control=SolidResultControl()
        )
    )
)
simulation_id = simulation.simulation_id

# Create mesh
print("Creating mesh...")
mesh_op = mesh_operations_api.create_mesh_operation(
    project_id,
    MeshOperation(
        name="Mesh",
        geometry_id=geometry_id,
        model=SimmetrixMeshingSolid(
            type="SIMMETRIX_MESHING_SOLID",
            sizing=AutomaticMeshSizingSimmetrix(type="AUTOMATIC_V9", fineness=5)
        )
    )
)

# Start meshing
mesh_operations_api.start_mesh_operation(
    project_id, mesh_op.mesh_operation_id, simulation_id=simulation_id
)

# Wait for mesh
print("Meshing...")
while True:
    mesh_op = mesh_operations_api.get_mesh_operation(project_id, mesh_op.mesh_operation_id)
    if mesh_op.status in ("FINISHED", "FAILED"):
        break
    time.sleep(30)

# Update simulation with mesh
sim = simulations_api.get_simulation(project_id, simulation_id)
sim.mesh_id = mesh_op.mesh_id
simulations_api.update_simulation(project_id, simulation_id, sim)

# Run simulation
print("Running simulation...")
run = simulation_runs_api.create_simulation_run(
    project_id, simulation_id, SimulationRun(name="Run 1")
)
simulation_runs_api.start_simulation_run(project_id, simulation_id, run.run_id)

# Wait for completion
while True:
    run = simulation_runs_api.get_simulation_run(project_id, simulation_id, run.run_id)
    print(f"Status: {run.status} - Progress: {run.progress:.0%}")
    if run.status in ("FINISHED", "FAILED"):
        break
    time.sleep(60)

print(f"\n✓ Simulation complete!")
print(f"View results at: https://www.simscale.com/workbench/project/{project_id}")