/*--------------------------------*- C++ -*----------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  10
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    location    "constant";
    object      physicalProperties.water;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

viscosityModel  constant;

nu                  3.7e-07;

rho                 8540;
elec_resistivity	1.0e-6;

poly_kappa          (6.484 0.012 0 0 0 0 0 0);
//poly_cp   (244.8 9.587e-1 -3.77e-4 6.5e-8 -4.14e-12 0 0 0);
poly_cp             (376.4 0.2 0 0 0 0 0 0);
    
Tsolidus            1573;
Tliquidus           1639;
LatentHeat          2.9e5;
beta                1.2e-4;


// ************************************************************************* //
