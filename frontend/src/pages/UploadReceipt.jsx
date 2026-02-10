import { useState, useCallback, useEffect } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { 
  Upload, Camera, CheckCircle, Loader2, MapPin, 
  Receipt, Phone, Store, Package, Trophy, AlertTriangle
} from "lucide-react";
import axios from "axios";
import { toast } from "sonner";
import { API } from "../App";

export default function UploadReceipt() {
  const [phoneNumber, setPhoneNumber] = useState("");
  const [image, setImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [location, setLocation] = useState(null);
  const [gettingLocation, setGettingLocation] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  // Auto-request location when page loads
  useEffect(() => {
    getLocation();
  }, []);

  // Get user's location
  const getLocation = () => {
    setGettingLocation(true);
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setLocation({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude
          });
          setGettingLocation(false);
          toast.success("Location captured for fraud verification!");
        },
        (error) => {
          console.error("Location error:", error);
          setGettingLocation(false);
          // Don't show error toast on auto-request - it might be denied silently
          if (error.code === error.PERMISSION_DENIED) {
            toast.warning("Location access denied. Distance verification won't be available.");
          }
        },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    } else {
      setGettingLocation(false);
      toast.error("Geolocation not supported by your browser");
    }
  };

  // Handle file selection
  const handleFile = (file) => {
    if (file && file.type.startsWith("image/")) {
      setImage(file);
      const reader = new FileReader();
      reader.onload = (e) => setImagePreview(e.target.result);
      reader.readAsDataURL(file);
    } else {
      toast.error("Please select an image file");
    }
  };

  // Handle drag and drop
  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  }, []);

  // Format phone number
  const formatPhoneNumber = (num) => {
    // Remove all non-digits
    let cleaned = num.replace(/\D/g, "");
    // Remove leading 0 and add 27
    if (cleaned.startsWith("0")) {
      cleaned = "27" + cleaned.substring(1);
    }
    // Add 27 if not present
    if (!cleaned.startsWith("27") && cleaned.length === 9) {
      cleaned = "27" + cleaned;
    }
    return cleaned;
  };

  // Submit receipt
  const handleSubmit = async () => {
    if (!phoneNumber) {
      toast.error("Please enter your phone number");
      return;
    }
    if (!image) {
      toast.error("Please upload a receipt image");
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      // Convert image to base64
      const reader = new FileReader();
      reader.onload = async (e) => {
        const base64 = e.target.result.split(",")[1];
        
        const response = await axios.post(`${API}/receipts/process-image`, {
          phone_number: formatPhoneNumber(phoneNumber),
          image_data: base64,
          mime_type: image.type,
          latitude: location?.latitude,
          longitude: location?.longitude
        });

        if (response.data.success !== false) {
          setResult(response.data);
          toast.success("Receipt processed! Check your WhatsApp!");
        } else {
          toast.error(response.data.error || "Failed to process receipt");
        }
        setLoading(false);
      };
      reader.readAsDataURL(image);
    } catch (error) {
      console.error("Upload error:", error);
      toast.error("Failed to process receipt");
      setLoading(false);
    }
  };

  // Reset form
  const handleReset = () => {
    setImage(null);
    setImagePreview(null);
    setResult(null);
  };

  return (
    <div className="min-h-screen p-4 md:p-6" data-testid="upload-receipt-page">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center"
        >
          <div className="w-16 h-16 rounded-2xl bg-primary/20 flex items-center justify-center mx-auto mb-4">
            <Receipt className="w-8 h-8 text-primary" />
          </div>
          <h1 className="text-3xl md:text-4xl font-heading font-bold mb-2">
            Upload Your Receipt
          </h1>
          <p className="text-muted-foreground">
            Snap, upload, and enter to win back your spend!
          </p>
        </motion.div>

        {/* Upload Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="glass-card rounded-2xl overflow-hidden">
            <CardHeader>
              <CardTitle className="font-heading flex items-center gap-2">
                <Camera className="w-5 h-5 text-primary" />
                {result ? "Receipt Processed!" : "Step 1: Your Details"}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {!result ? (
                <>
                  {/* Phone Number */}
                  <div className="space-y-2">
                    <Label htmlFor="phone" className="text-sm font-medium flex items-center gap-2">
                      <Phone className="w-4 h-4" />
                      WhatsApp Number
                    </Label>
                    <Input
                      id="phone"
                      type="tel"
                      placeholder="076 969 5462"
                      value={phoneNumber}
                      onChange={(e) => setPhoneNumber(e.target.value)}
                      className="bg-white/5 border-white/10 text-lg"
                      data-testid="phone-input"
                    />
                    <p className="text-xs text-muted-foreground">
                      You'll receive confirmation on this number
                    </p>
                  </div>

                  {/* Location */}
                  <div className="space-y-2">
                    <Label className="text-sm font-medium flex items-center gap-2">
                      <MapPin className="w-4 h-4" />
                      Your Location
                      <Badge variant="outline" className="text-xs">Required for verification</Badge>
                    </Label>
                    {location ? (
                      <div className="flex items-center gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                        <CheckCircle className="w-5 h-5 text-green-500" />
                        <span className="text-sm text-green-400">
                          Location captured ({location.latitude.toFixed(4)}, {location.longitude.toFixed(4)})
                        </span>
                      </div>
                    ) : (
                      <Button
                        variant="outline"
                        onClick={getLocation}
                        disabled={gettingLocation}
                        className="w-full border-orange-500/30 hover:bg-orange-500/10"
                        data-testid="get-location-btn"
                      >
                        {gettingLocation ? (
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                          <MapPin className="w-4 h-4 mr-2 text-orange-500" />
                        )}
                        {gettingLocation ? "Getting location..." : "Enable Location Sharing"}
                      </Button>
                    )}
                    {!location && !gettingLocation && (
                      <p className="text-xs text-orange-400">
                        Location helps verify you're near the shop for fraud prevention
                      </p>
                    )}
                  </div>

                  {/* Image Upload */}
                  <div className="space-y-2">
                    <Label className="text-sm font-medium flex items-center gap-2">
                      <Upload className="w-4 h-4" />
                      Receipt Photo
                    </Label>
                    
                    <div
                      className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
                        dragActive 
                          ? "border-primary bg-primary/10" 
                          : imagePreview 
                            ? "border-green-500/50 bg-green-500/5" 
                            : "border-white/20 hover:border-white/40"
                      }`}
                      onDragEnter={handleDrag}
                      onDragLeave={handleDrag}
                      onDragOver={handleDrag}
                      onDrop={handleDrop}
                      data-testid="drop-zone"
                    >
                      {imagePreview ? (
                        <div className="space-y-4">
                          <img
                            src={imagePreview}
                            alt="Receipt preview"
                            className="max-h-64 mx-auto rounded-lg shadow-lg"
                          />
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleReset}
                            className="text-muted-foreground"
                          >
                            Remove & upload different receipt
                          </Button>
                        </div>
                      ) : (
                        <div className="space-y-4">
                          <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mx-auto">
                            <Camera className="w-8 h-8 text-muted-foreground" />
                          </div>
                          <div>
                            <p className="text-lg font-medium">
                              Drop your receipt here
                            </p>
                            <p className="text-sm text-muted-foreground">
                              or click to browse
                            </p>
                          </div>
                          <input
                            type="file"
                            accept="image/*"
                            capture="environment"
                            onChange={(e) => handleFile(e.target.files[0])}
                            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                            data-testid="file-input"
                          />
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Submit Button */}
                  <Button
                    onClick={handleSubmit}
                    disabled={loading || !phoneNumber || !image}
                    className="w-full h-14 text-lg font-semibold rounded-xl"
                    data-testid="submit-btn"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                        Processing...
                      </>
                    ) : (
                      <>
                        <Trophy className="w-5 h-5 mr-2" />
                        Submit & Enter Draw
                      </>
                    )}
                  </Button>
                </>
              ) : (
                /* Success Result */
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="space-y-6"
                >
                  <div className="text-center">
                    <div className="w-20 h-20 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-4">
                      <CheckCircle className="w-10 h-10 text-green-500" />
                    </div>
                    <h2 className="text-2xl font-bold text-green-400 mb-2">
                      You're In The Draw!
                    </h2>
                    <p className="text-muted-foreground">
                      Check your WhatsApp for confirmation
                    </p>
                  </div>

                  {result.receipt && (
                    <div className="space-y-4 p-4 rounded-xl bg-white/5 border border-white/10">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Store className="w-5 h-5 text-primary" />
                          <span className="font-semibold">{result.receipt.shop_name}</span>
                        </div>
                        <Badge className={
                          result.receipt.fraud_flag === "valid" 
                            ? "bg-green-500/20 text-green-400" 
                            : "bg-yellow-500/20 text-yellow-400"
                        }>
                          {result.receipt.fraud_flag === "valid" ? (
                            <><CheckCircle className="w-3 h-3 mr-1" /> Verified</>
                          ) : (
                            <><AlertTriangle className="w-3 h-3 mr-1" /> Review</>
                          )}
                        </Badge>
                      </div>
                      
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div className="p-3 rounded-lg bg-white/5">
                          <p className="text-muted-foreground text-xs mb-1">Amount</p>
                          <p className="font-mono text-xl font-bold text-primary">
                            R{result.receipt.amount?.toFixed(2)}
                          </p>
                        </div>
                        <div className="p-3 rounded-lg bg-white/5">
                          <p className="text-muted-foreground text-xs mb-1">Items</p>
                          <p className="font-mono text-xl font-bold">
                            {result.receipt.items?.length || 0}
                          </p>
                        </div>
                      </div>

                      {result.receipt.items && result.receipt.items.length > 0 && (
                        <div className="space-y-2">
                          <p className="text-xs text-muted-foreground flex items-center gap-1">
                            <Package className="w-3 h-3" /> Items Extracted
                          </p>
                          <div className="max-h-32 overflow-y-auto space-y-1">
                            {result.receipt.items.slice(0, 5).map((item, i) => (
                              <div key={i} className="flex justify-between text-sm py-1 border-b border-white/5">
                                <span className="truncate">{item.name}</span>
                                <span className="font-mono text-primary">R{item.price?.toFixed(2)}</span>
                              </div>
                            ))}
                            {result.receipt.items.length > 5 && (
                              <p className="text-xs text-muted-foreground">
                                +{result.receipt.items.length - 5} more items
                              </p>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  <div className="flex gap-3">
                    <Button
                      variant="outline"
                      onClick={handleReset}
                      className="flex-1"
                    >
                      Upload Another
                    </Button>
                    <Button
                      onClick={() => window.location.href = "/draws"}
                      className="flex-1"
                    >
                      <Trophy className="w-4 h-4 mr-2" />
                      View Draws
                    </Button>
                  </div>
                </motion.div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Info Cards */}
        {!result && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="grid grid-cols-3 gap-3 text-center"
          >
            <div className="p-4 rounded-xl bg-white/5 border border-white/10">
              <Camera className="w-6 h-6 text-primary mx-auto mb-2" />
              <p className="text-xs font-medium">Snap</p>
              <p className="text-xs text-muted-foreground">Take a photo</p>
            </div>
            <div className="p-4 rounded-xl bg-white/5 border border-white/10">
              <Upload className="w-6 h-6 text-secondary mx-auto mb-2" />
              <p className="text-xs font-medium">Upload</p>
              <p className="text-xs text-muted-foreground">Submit receipt</p>
            </div>
            <div className="p-4 rounded-xl bg-white/5 border border-white/10">
              <Trophy className="w-6 h-6 text-yellow-500 mx-auto mb-2" />
              <p className="text-xs font-medium">Win</p>
              <p className="text-xs text-muted-foreground">Daily draw</p>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
