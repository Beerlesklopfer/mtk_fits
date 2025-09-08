document.addEventListener('DOMContentLoaded', function() {
    const canvas = document.getElementById('toleranceCanvas');
    const ctx = canvas.getContext('2d');
    
    // UI Elements
    const nominalSizeInput = document.getElementById('nominal_size');
    const holeToleranceSelect = document.getElementById('hole-tolerance');
    const holeGradeSelect = document.getElementById('hole-grade');
    const shaftToleranceSelect = document.getElementById('shaft-tolerance');
    const shaftGradeSelect = document.getElementById('shaft-grade');
    
    // Info Elements
    const fitTypeElement = document.getElementById('fit-type');
    const maxClearanceElement = document.getElementById('max-clearance');
    const minClearanceElement = document.getElementById('min-clearance');
    const fitSystemElement = document.getElementById('fit-system');
    
   
    // Update function
    // function updateVisualization(nominalSize, holeTolerance, holeGrade, shaftTolerance, shaftGrade) {
    //     nominalSize = parseFloat(nominalSize);
    //     holeTolerance = holeTolerance;
    //     holeGrade = holeGrade;
    //     shaftTolerance = shaftTolerance;
    //     shaftGrade = shaftGrade;
        
    //     updateFitInfo();
    // }
    
    // Event listeners
    // nominalSizeInput.addEventListener('input', updateVisualization);
    // holeToleranceSelect.addEventListener('change', updateVisualization);
    // holeGradeSelect.addEventListener('change', updateVisualization);
    // shaftToleranceSelect.addEventListener('change', updateVisualization);
    // shaftGradeSelect.addEventListener('change', updateVisualization);
    
    // Calculate tolerance values based on ISO 286
    function calculateTolerance(size, grade, deviation) {
        // Simplified calculation for demonstration
        // In a real application, you would use the complete ISO 286 standard tables
               
        const factor = gradeFactors[grade] || 10;
        const devFactor = deviationFactors[deviation] || 0;
        
        // Calculate tolerance values
        const tolerance = (size * factor / 100);
        
        // Calculate upper and lower deviations
        let upperDeviation, lowerDeviation;
        
        if (deviation === deviation.toUpperCase()) {
            // Hole basis
            lowerDeviation = devFactor * tolerance / 2;
            upperDeviation = lowerDeviation + tolerance;
        } else {
            // Shaft basis
            upperDeviation = -devFactor * tolerance / 2;
            lowerDeviation = upperDeviation - tolerance;
        }
        
        const maxSize = size + upperDeviation;
        const minSize = size + lowerDeviation;
        
        return {
            tolerance,
            upperDeviation,
            lowerDeviation,
            maxSize,
            minSize
        };
    }
    
    // Update fit information
    // function updateFitInfo() {
    //     const holeData = calculateTolerance(nominalSize, holeGrade, holeTolerance);
    //     const shaftData = calculateTolerance(nominalSize, shaftGrade, shaftTolerance);
        
    //     // Calculate clearance
    //     const maxClearance = holeData.maxSize - shaftData.minSize;
    //     const minClearance = holeData.minSize - shaftData.maxSize;
        
    //     // Determine fit type
    //     let fitType;
    //     if (minClearance > 0) {
    //         fitType = "Spielpassung";
    //     } else if (maxClearance < 0) {
    //         fitType = "Übermaßpassung";
    //     } else {
    //         fitType = "Übergangspassung";
    //     }
        
    //     // Determine fit system
    //     const fitSystem = holeTolerance === 'H' ? "Einheitsbohrung" : (shaftTolerance === 'h' ? "Einheitswelle" : "Kombiniertes System");
        
    //     // Update UI
    //     fitTypeElement.textContent = fitType;
    //     maxClearanceElement.textContent = `${maxClearance.toFixed(3)} mm`;
    //     minClearanceElement.textContent = `${minClearance.toFixed(3)} mm`;
    //     fitSystemElement.textContent = fitSystem;
    // }
// Draw tolerance chart

function drawToleranceChart(objCanvas, objCtx, 
                    objHoleES, objHoleEI, 
                    objShaftES, objShaftEI, 
                    objNominalSize) {

    // Draw the tolerance chart
        const width = objCanvas.width;
        const height = objCanvas.height;
        const padding = 60;
        const chartWidth = width - 2 * padding;
        const chartHeight = height - 2 * padding;
        
        // Clear canvas
        objCtx.clearRect(0, 0, width, height);
        
        // Calculate tolerance values
        const holeData = calculateTolerance(nominalSize, holeGrade, holeTolerance);
        const shaftData = calculateTolerance(nominalSize, shaftGrade, shaftTolerance);
        
        // Determine min and max values for scaling
        const allValues = [
            holeData.maxSize, holeData.minSize, 
            shaftData.maxSize, shaftData.minSize, 
            nominalSize
        ];
        
        const maxValue = Math.max(...allValues) * 1.05;
        const minValue = Math.min(...allValues) * 0.95;
        const valueRange = maxValue - minValue;
        
        // Calculate scaling factors
        const scale = chartHeight / valueRange;
        
        // Function to calculate Y position from size value
        const getYPos = (value) => {
            return height - padding - (value - minValue) * scale;
        };
        
        // Draw axes
        objCtx.beginPath();
        objCtx.moveTo(padding, padding);
        objCtx.lineTo(padding, height - padding);
        objCtx.lineTo(width - padding, height - padding);
        objCtx.strokeStyle = '#2c3e50';
        objCtx.lineWidth = 2;
        objCtx.stroke();
        
        // Draw axis labels
        objCtx.font = '14px Arial';
        objCtx.fillStyle = '#2c3e50';
        objCtx.textAlign = 'center';
        objCtx.textBaseline = 'middle';
        
        // X-axis label
        objCtx.fillText('Toleranzzonen', width / 2, height - 20);
        
        // Y-axis label
        objCtx.save();
        objCtx.translate(20, height / 2);
        objCtx.rotate(-Math.PI / 2);
        objCtx.fillText('Maß (mm)', 0, 0);
        objCtx.restore();
        
        // Draw grid lines and labels
        objCtx.textAlign = 'right';
        objCtx.textBaseline = 'middle';
        const steps = 5;
        for (let i = 0; i <= steps; i++) {
            const value = minValue + (i / steps) * valueRange;
            const y = getYPos(value);
            
            // Grid line
            objCtx.beginPath();
            objCtx.moveTo(padding, y);
            objCtx.lineTo(width - padding, y);
            objCtx.strokeStyle = '#ecf0f1';
            objCtx.lineWidth = 1;
            objCtx.stroke();
            
            // Label
            objCtx.fillStyle = '#7f8c8d';
            objCtx.fillText(value.toFixed(2), padding - 10, y);
        }
        
        // Draw tolerance zones
        const holeZoneTop = getYPos(holeData.maxSize);
        const holeZoneBottom = getYPos(holeData.minSize);
        const shaftZoneTop = getYPos(shaftData.maxSize);
        const shaftZoneBottom = getYPos(shaftData.minSize);
        
        // Draw hole tolerance zone
        objCtx.fillStyle = 'rgba(231, 76, 60, 0.2)';
        objCtx.fillRect(padding + 50, holeZoneTop, 150, holeZoneBottom - holeZoneTop);
        objCtx.strokeStyle = '#e74c3c';
        objCtx.lineWidth = 2;
        objCtx.strokeRect(padding + 50, holeZoneTop, 150, holeZoneBottom - holeZoneTop);
        
        // Draw shaft tolerance zone
        objCtx.fillStyle = 'rgba(52, 152, 219, 0.2)';
        objCtx.fillRect(padding + 250, shaftZoneTop, 150, shaftZoneBottom - shaftZoneTop);
        objCtx.strokeStyle = '#3498db';
        objCtx.lineWidth = 2;
        objCtx.strokeRect(padding + 250, shaftZoneTop, 150, shaftZoneBottom - shaftZoneTop);
        
        // Draw nominal size line
        const nominalY = getYPos(nominalSize);
        objCtx.beginPath();
        objCtx.moveTo(padding, nominalY);
        objCtx.lineTo(width - padding, nominalY);
        objCtx.setLineDash([5, 3]);
        objCtx.strokeStyle = '#9b59b6';
        objCtx.lineWidth = 2;
        objCtx.stroke();
        objCtx.setLineDash([]);
        
        // Draw labels for tolerance zones
        objCtx.font = 'bold 16px Arial';
        objCtx.textAlign = 'center';
        
        // Hole label
        objCtx.fillStyle = '#e74c3c';
        objCtx.fillText(`Bohrung: ${holeTolerance}${holeGrade}`, padding + 125, holeZoneTop - 20);
        objCtx.fillText(`Ø ${holeData.maxSize.toFixed(3)}`, padding + 125, holeZoneTop - 5);
        objCtx.fillText(`Ø ${holeData.minSize.toFixed(3)}`, padding + 125, holeZoneBottom + 15);
        
        // Shaft label
        objCtx.fillStyle = '#3498db';
        objCtx.fillText(`Welle: ${shaftTolerance}${shaftGrade}`, padding + 325, shaftZoneTop - 20);
        objCtx.fillText(`Ø ${shaftData.maxSize.toFixed(3)}`, padding + 325, shaftZoneTop - 5);
        objCtx.fillText(`Ø ${shaftData.minSize.toFixed(3)}`, padding + 325, shaftZoneBottom + 15);
        
        // Draw nominal size label
        objCtx.fillStyle = '#9b59b6';
        objCtx.fillText(`Nennmaß: Ø ${nominalSize}`, width - 150, nominalY - 15);
        
        // Draw tolerance symbols
        objCtx.font = '20px Arial';
        objCtx.fillStyle = '#2c3e50';
        objCtx.fillText("↥", padding + 125, holeZoneTop - 40);
        objCtx.fillText("↧", padding + 125, holeZoneBottom + 35);
        objCtx.fillText("↥", padding + 325, shaftZoneTop - 40);
        objCtx.fillText("↧", padding + 325, shaftZoneBottom + 35);
        
        // Draw comparison diagram
        const comparisonX = padding + 500;
        const comparisonWidth = 150;
        
        // Draw hole in comparison
        objCtx.beginPath();
        objCtx.arc(comparisonX, nominalY, nominalSize/2, 0, Math.PI * 2);
        objCtx.strokeStyle = '#e74c3c';
        objCtx.lineWidth = 3;
        objCtx.stroke();
        
        // Draw shaft in comparison
        objCtx.beginPath();
        objCtx.arc(comparisonX, nominalY, nominalSize/2 - 5, 0, Math.PI * 2);
        objCtx.strokeStyle = '#3498db';
        objCtx.lineWidth = 3;
        objCtx.stroke();
        
        // Draw clearance
        const clearance = holeData.minSize - shaftData.maxSize;
        if (clearance > 0) {
            objCtx.beginPath();
            objCtx.arc(comparisonX, nominalY, nominalSize/2 - 2.5, 0, Math.PI * 2);
            objCtx.setLineDash([2, 2]);
            objCtx.strokeStyle = '#2ecc71';
            objCtx.lineWidth = 1;
            objCtx.stroke();
            objCtx.setLineDash([]);
            
            // Draw clearance indicator
            objCtx.beginPath();
            objCtx.moveTo(comparisonX + nominalSize/2 + 5, nominalY);
            objCtx.lineTo(comparisonX + nominalSize/2 + 20, nominalY);
            objCtx.strokeStyle = '#2c3e50';
            objCtx.lineWidth = 1;
            objCtx.stroke();
            
            objCtx.beginPath();
            objCtx.moveTo(comparisonX + nominalSize/2 + 5, nominalY - 10);
            objCtx.lineTo(comparisonX + nominalSize/2 + 5, nominalY + 10);
            objCtx.stroke();
            
            objCtx.beginPath();
            objCtx.moveTo(comparisonX + nominalSize/2 + 20, nominalY - 10);
            objCtx.lineTo(comparisonX + nominalSize/2 + 20, nominalY + 10);
            objCtx.stroke();
            
            objCtx.font = '12px Arial';
            objCtx.fillStyle = '#2c3e50';
            objCtx.fillText(`Spiel: ${clearance.toFixed(3)}mm`, comparisonX + nominalSize/2 + 40, nominalY);
        }
        
    }
    
    // Initial draw
    // updateVisualization();
});