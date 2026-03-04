import React from 'react';
import { MagneticParticles } from './MagneticParticles';

export function MakemakeParticles(props) {
    return (
        <MagneticParticles
            {...props}
            particleCount={1500}
            planetRadius={3.0}
            rmaxRange={[7.0, 16.0]}
            baseSpeed={0.15}
            pointSize={2.0}
            cycleSpeed={0.5}
            arcBands={3}
            shellBands={5}
            tilt={[0.2, 0, 0.15]}
        />
    );
}
