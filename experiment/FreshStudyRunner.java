package study;

import com.google.gson.*;
import edu.university.ecs.lab.common.models.ir.*;
import edu.university.ecs.lab.common.models.enums.ClassRole;
import edu.university.ecs.lab.common.utils.JsonReadWriteUtils;
import edu.university.ecs.lab.intermediate.create.services.IRExtractionService;
import edu.university.ecs.lab.detection.metrics.RunCohesionMetrics;
import edu.university.ecs.lab.detection.metrics.models.*;
import edu.university.ecs.lab.detection.metrics.services.*;
import java.nio.file.*;
import java.util.*;
import java.lang.reflect.Field;

public class FreshStudyRunner {
  static final Gson GSON = new GsonBuilder().setPrettyPrinting().serializeNulls().create();
  static ServiceDescriptor descriptor(Microservice service) {
    ServiceDescriptor d = new ServiceDescriptor();
    d.setServiceName(service.getName());
    List<Operation> operations = new ArrayList<>();
    List<JClass> controllers = new ArrayList<>(service.getControllers());
    controllers.sort(Comparator.comparing(JClass::getPath));
    for (JClass controller : controllers) {
      List<edu.university.ecs.lab.common.models.ir.Method> methods = new ArrayList<>(controller.getMethods());
      methods.sort(Comparator.comparing(edu.university.ecs.lab.common.models.ir.Method::getName));
      for (edu.university.ecs.lab.common.models.ir.Method m : methods) {
        Operation o = new Operation();
        o.setName(controller.getPath()+"::"+m.getName());
        o.setResponseType(m.getReturnType());
        List<String> parameters = new ArrayList<>();
        for (edu.university.ecs.lab.common.models.ir.Parameter a : m.getParameters()) parameters.add(a.getType());
        o.setParamList(parameters);
        List<String> annotations = new ArrayList<>();
        for (Annotation a : m.getAnnotations()) annotations.add(a.getName()+" - "+a.getContents());
        o.setUsingTypesList(annotations);
        operations.add(o);
      }
    }
    d.setServiceOperations(operations);
    return d;
  }
  static JsonObject assess(ServiceDescriptor descriptor) throws Exception {
    JsonObject values = new JsonObject();
    Field raw = MetricResult.class.getDeclaredField("metricValue");
    raw.setAccessible(true);
    for (MetricResult r : new MetricCalculator().assess(descriptor)) {
      Double value = (Double)raw.get(r);
      JsonObject record = new JsonObject();
      boolean finite = value != null && Double.isFinite(value);
      record.addProperty("finite",finite);
      if (finite) record.addProperty("value",value); else record.add("value",JsonNull.INSTANCE);
      values.add(r.getMetricName(),record);
    }
    return values;
  }
  static void write(Path target,Object data) throws Exception {
    if (target.getParent()!=null) Files.createDirectories(target.getParent());
    Files.writeString(target,GSON.toJson(data));
  }
  static void selfTest(Path output) throws Exception {
    Microservice service = new Microservice("fixture","/fixture");
    for (int i=0;i<2;i++) {
      JClass controller = new JClass("C"+i,"/fixture/C"+i+".java","test",ClassRole.CONTROLLER);
      edu.university.ecs.lab.common.models.ir.Method m = new edu.university.ecs.lab.common.models.ir.Method();
      m.setName("operation"+i); m.setReturnType("String");
      m.setParameters(new HashSet<>()); m.setAnnotations(new HashSet<>());
      controller.getMethods().add(m); service.getControllers().add(controller);
    }
    ServiceDescriptor d=descriptor(service);
    if (d.getServiceOperations().size()!=2) throw new IllegalStateException("two-controller fixture failed");
    JsonObject result=assess(d);
    double lomlc=result.getAsJsonObject("LackOfMessageLevelCohesion").get("value").getAsDouble();
    if (lomlc!=0.0) throw new IllegalStateException("identical I/O fixture failed");
    if (result.getAsJsonObject("StrictServiceImplementationCohesion").get("finite").getAsBoolean())
      throw new IllegalStateException("non-finite SSIC must remain distinguishable from zero");
    JsonObject report=new JsonObject();
    report.addProperty("status","pass");
    report.addProperty("controller_count",2);
    report.addProperty("operation_count",2);
    report.addProperty("lomlc",lomlc);
    report.addProperty("nonfinite_ssic_preserved",true);
    write(output,report);
  }
  public static void main(String[] args) throws Exception {
    if (args.length==2 && args[0].equals("--self-test")) { selfTest(Path.of(args[1])); return; }
    if(args.length!=3) throw new IllegalArgumentException("configPath commitSha outputPrefix");
    Path prefix=Path.of(args[2]);
    if(prefix.getParent()!=null) Files.createDirectories(prefix.getParent());
    String irPath=args[2]+".ir.json";
    new IRExtractionService(args[0],Optional.of(args[1])).generateIR(irPath);
    MicroserviceSystem system=JsonReadWriteUtils.readFromJSON(irPath,MicroserviceSystem.class);
    JsonArray rows=new JsonArray();
    List<Microservice> services=new ArrayList<>(system.getMicroservices());
    services.sort(Comparator.comparing(Microservice::getPath));
    for(Microservice service:services) {
      ServiceDescriptor d=descriptor(service);
      JsonObject row=new JsonObject();
      row.addProperty("service_name",service.getName());
      row.addProperty("path",service.getPath());
      row.addProperty("controllers",service.getControllers().size());
      row.addProperty("operations",d.getServiceOperations().size());
      row.addProperty("http_endpoints",service.getEndpoints().size());
      row.addProperty("cohesion_applicable",d.getServiceOperations().size()>=2);
      row.addProperty("deployable_service_validated",false);
      row.add("all_controllers_metrics",assess(d));
      rows.add(row);
    }
    JsonObject result=new JsonObject();
    result.addProperty("commit_sha",args[1]);
    result.addProperty("cimet_base","15cfacb6f5b357d0b61b59a6184b19a41bf11741");
    result.addProperty("status","raw_measurement_not_architecture_validation");
    result.add("components",rows);
    try {
      result.add("upstream_legacy_aggregate",GSON.toJsonTree(RunCohesionMetrics.calculateCohesionMetrics(irPath).getMetrics()));
    } catch(Exception ex) {
      result.addProperty("upstream_aggregate_error",ex.getClass().getSimpleName());
    }
    write(Path.of(args[2]+".metrics.json"),result);
  }
}
