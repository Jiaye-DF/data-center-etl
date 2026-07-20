import java.sql.*;
import java.io.*;
import java.util.Properties;
public class Q2 {
  public static void main(String[] a) throws Exception {
    PrintStream out = new PrintStream(new FileOutputStream(FileDescriptor.out), true, "UTF-8");
    Properties cfg = new Properties();
    try (Reader rd = new InputStreamReader(new FileInputStream(
        a.length > 0 ? a[0] : "db.properties"), "UTF-8")) { cfg.load(rd); }
    String url = cfg.getProperty("url");
    StringBuilder sb = new StringBuilder();
    BufferedReader br = new BufferedReader(new InputStreamReader(System.in, "UTF-8"));
    String line; while ((line=br.readLine())!=null) sb.append(line).append("\n");
    String sql = sb.toString().trim();
    if (sql.endsWith(";")) sql = sql.substring(0, sql.length()-1);
    Properties p = new Properties();
    p.put("user", cfg.getProperty("user"));
    p.put("password", cfg.getProperty("password"));
    if ("true".equalsIgnoreCase(cfg.getProperty("sysdba"))) p.put("internal_logon", "sysdba");
    try (Connection c = DriverManager.getConnection(url, p)) {
      c.setReadOnly(true);
      Statement s = c.createStatement();
      s.setFetchSize(500);
      ResultSet r = s.executeQuery(sql);
      ResultSetMetaData m = r.getMetaData();
      int n = m.getColumnCount();
      StringBuilder h = new StringBuilder();
      for (int i=1;i<=n;i++){ if(i>1)h.append("\t"); h.append(m.getColumnName(i)); }
      out.println(h);
      int cnt=0;
      while (r.next()){
        StringBuilder rb = new StringBuilder();
        for (int i=1;i<=n;i++){ if(i>1)rb.append("\t"); String v=r.getString(i); rb.append(v==null?"":v.replace("\t"," ").replace("\r"," ").replace("\n"," ")); }
        out.println(rb); cnt++;
      }
      System.err.println("ROWS="+cnt);
    } catch (Exception e){ System.err.println("SQLERR: "+e.getMessage()); }
  }
}
